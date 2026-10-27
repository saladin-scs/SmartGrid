"""Extract, validate, preview, and persist natural-language RDF individuals."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

from rdflib import Literal, URIRef
from rdflib.namespace import RDF, XSD
from rdflib.term import Identifier

from web_sem.nlp.aliases import SUBJECTS, alias_index
from web_sem.nlp.catalog import all_class_names, is_ancestor, locate
from web_sem.nlp.interpret import MAX_QUESTION
from web_sem.nlp.normalize import normalized_question
from web_sem.ontology import (
    LOCAL_NAME_RE,
    MAX_LOCAL_NAME,
    ONTOLOGY_NS,
    OntologyModule,
    OntologyProperty,
    display_name,
    get_property,
    individual_iri,
    list_properties,
    reserved_names,
)

if TYPE_CHECKING:
    from web_sem.repository import IndividualRepository

_CREATE_ACTIONS = frozenset(
    {
        "creer",
        "cree",
        "creez",
        "ajouter",
        "ajoute",
        "ajoutez",
        "enregistrer",
        "enregistre",
        "enregistrez",
        "ajout",
        "creation",
    }
)
_CLASS_STOPWORDS = frozenset(
    {
        "a", "au", "aux", "avec", "d", "dans", "de", "des", "du",
        "et", "la", "le", "les", "un", "une",
    }
)
_NAME_CUE = re.compile(
    r"\b(?:(?:appel[ée]e?|nomm[ée]e?)|s['’]appelle|ayant\s+pour\s+nom|de\s+nom|nom)\s+"
    r"(?!de\s+(?:la\s+)?(?:zone|personne)\b)"
    r"(?P<name>[\wÀ-ÿ][\wÀ-ÿ -]*?)"
    r"(?=\s+(?:avec\b|et\b|dans\s+la\s+(?:région|region|zone|ville)\b|"
    r"situ[ée]e?\s+dans\b|localis[ée]e?\s+dans\b|se\s+trouve\s+dans\b|"
    r"région\b|region\b|puissance\b)|[,;.!?]|$)",
    re.IGNORECASE,
)
_PROPERTY_ASSIGNMENT = re.compile(
    r"(?P<key>[A-Za-zÀ-ÿ][\wÀ-ÿ]*(?:\s+[A-Za-zÀ-ÿ][\wÀ-ÿ]*)?)"
    r"\s*(?:=|:)\s*(?P<value>[^,;\n]+?)"
    r"(?=\s*(?:[,;]|[.!?](?:\s|$)|$)|\s+et\s+(?=[A-Za-zÀ-ÿ][\wÀ-ÿ ]*\s*(?:=|:)))",
)
_DATATYPE_VALUES = {
    str(XSD.string),
    str(XSD.date),
    str(XSD.dateTime),
    str(XSD.integer),
    str(XSD.decimal),
    str(XSD.boolean),
}
_NATURAL_PROPERTY_ALIASES = {
    "nomZone": ("nom de la zone", "nom zone"),
    "region": ("dans la région", "dans la region", "région", "region"),
    "puissanceInstalleeMW": ("puissance installée", "puissance installee"),
    "estSitueDans": (
        "situé dans la zone",
        "située dans la zone",
        "situé dans une zone",
        "située dans une zone",
        "localisé dans la zone",
        "localisée dans la zone",
        "se trouve dans la zone",
        "situé dans",
        "située dans",
        "localisé dans",
        "localisée dans",
        "se trouve dans",
        "dans la zone",
        "dans une zone",
        "dans la ville",
        "dans une ville",
    ),
}


class CreationError(ValueError):
    """The description cannot safely be mapped to ontology-backed RDF."""


@dataclass(frozen=True, slots=True)
class CreationProperty:
    local_name: str
    label: str
    value: str
    is_object: bool
    iri_value: str = ""


@dataclass(frozen=True, slots=True)
class CreationPreview:
    local_name: str
    individual_iri: str
    class_name: str
    class_label: str
    module: OntologyModule
    properties: tuple[CreationProperty, ...]
    triples: tuple[tuple[URIRef, URIRef, Identifier], ...]

    @property
    def rendered_triples(self) -> tuple[str, ...]:
        return tuple(
            f"{subject.n3()} {predicate.n3()} {value.n3()} ."
            for subject, predicate, value in self.triples
        )


def prepare_creation(
    description: str,
    repository: IndividualRepository,
) -> CreationPreview:
    """Resolve a description against the ontology and build validated RDF terms."""
    if not isinstance(description, str) or not description.strip():
        raise CreationError("Décrivez l’individu à créer.")
    if len(description) > MAX_QUESTION:
        raise CreationError("La description dépasse la longueur autorisée.")

    normalized = normalized_question(description)
    if not _CREATE_ACTIONS.intersection(normalized.split()):
        raise CreationError("Précisez une action, par exemple « créer » ou « ajouter ».")

    name_matches = list(_NAME_CUE.finditer(description))
    if len(name_matches) > 1:
        raise CreationError("La description contient plusieurs noms possibles.")
    name_match = name_matches[0] if name_matches else None
    property_values = _extract_property_values(description)
    class_text = description
    if name_match:
        class_text = class_text[: name_match.start()] + class_text[name_match.end() :]
    class_text = _PROPERTY_ASSIGNMENT.sub(" ", class_text)
    class_text = _strip_natural_property_clauses(class_text)
    class_name = _resolve_class(class_text)
    if name_match:
        name_value = name_match.group("name")
    else:
        name_value = _infer_name(class_text, class_name)
    local_name = _local_name(name_value)
    try:
        subject = URIRef(individual_iri(local_name))
    except ValueError as exc:
        raise CreationError(
            "Le nom doit commencer par une lettre et ne contenir que des lettres, "
            "des chiffres ou des traits de soulignement."
        ) from exc
    if local_name in reserved_names():
        raise CreationError("Ce nom est déjà réservé par une classe ou propriété de l’ontologie.")
    if repository.exists(local_name):
        raise CreationError(f"L’individu « {local_name} » existe déjà.")

    found = locate(class_name)
    if found is None:
        raise CreationError("La classe sélectionnée n’existe pas dans ENERGIE.rdf.")
    module, ontology_class = found

    triples: list[tuple[URIRef, URIRef, Identifier]] = [
        (subject, RDF.type, URIRef(ontology_class.iri))
    ]
    preview_properties: list[CreationProperty] = []
    for property_name, raw_value in property_values.items():
        ontology_property = get_property(property_name)
        if ontology_property is None:
            raise CreationError(f"La propriété « {property_name} » n’existe pas dans l’ontologie.")
        _validate_domain(ontology_property, class_name)
        predicate = URIRef(ontology_property.iri)
        if ontology_property.is_object:
            value_iri = _object_value_iri(
                raw_value,
                ontology_property.ranges,
                repository,
            )
            value_term = URIRef(value_iri)
            property_value = CreationProperty(
                property_name,
                display_name(property_name),
                value_iri,
                True,
                value_iri,
            )
        else:
            value_term = _literal_value(raw_value, ontology_property.ranges)
            property_value = CreationProperty(
                property_name,
                display_name(property_name),
                str(value_term),
                False,
            )
        triples.append((subject, predicate, value_term))
        preview_properties.append(property_value)

    return CreationPreview(
        local_name=local_name,
        individual_iri=str(subject),
        class_name=class_name,
        class_label=ontology_class.display_name,
        module=module,
        properties=tuple(preview_properties),
        triples=tuple(triples),
    )


def persist_creation(
    preview: CreationPreview,
    repository: IndividualRepository,
) -> None:
    """Write only validated triples, serialized by RDFLib, through Fuseki."""
    if repository.exists(preview.local_name):
        raise CreationError(f"L’individu « {preview.local_name} » existe déjà.")
    if not preview.triples or preview.triples[0] != (
        URIRef(preview.individual_iri),
        RDF.type,
        URIRef(preview.module.classes_by_name[preview.class_name].iri),
    ):
        raise CreationError("La prévisualisation RDF n’est plus valide.")
    update = "INSERT DATA { " + " ".join(preview.rendered_triples) + " }"
    repository.service.update(update)


def _local_name(value: str) -> str:
    candidate = value.strip().strip("«»\"'`").strip()
    if LOCAL_NAME_RE.fullmatch(candidate) and len(candidate) <= MAX_LOCAL_NAME:
        return candidate
    ascii_name = unicodedata.normalize("NFKD", candidate).encode("ascii", "ignore").decode()
    parts = re.findall(r"[A-Za-z0-9]+", ascii_name)
    if not parts:
        raise CreationError("Le nom indiqué ne peut pas former un identifiant RDF.")
    local_name = "".join(part[:1].upper() + part[1:] for part in parts)
    if not LOCAL_NAME_RE.fullmatch(local_name) or len(local_name) > MAX_LOCAL_NAME:
        raise CreationError("Le nom indiqué ne peut pas former un identifiant RDF valide.")
    return local_name


def _resolve_class(class_text: str) -> str:
    words = [
        word for word in normalized_question(class_text).split()
        if word not in _CLASS_STOPWORDS
    ]
    scores: dict[str, int] = {}
    forms: list[tuple[str, tuple[str, ...]]] = []
    for local_name in all_class_names():
        phrase = tuple(
            word for word in normalized_question(display_name(local_name)).split()
            if word not in _CLASS_STOPWORDS
        )
        forms.append((local_name, phrase))
    for alias in alias_index():
        phrase = tuple(word for word in alias.phrase.split() if word not in _CLASS_STOPWORDS)
        forms.append((alias.local_name, phrase))

    for local_name, phrase in forms:
        if not phrase:
            continue
        width = _longest_common_run(words, phrase)
        if width:
            score = width * 1000 - len(phrase)
            scores[local_name] = max(scores.get(local_name, 0), score)
    if not scores:
        raise CreationError("Aucune classe de l’ontologie ne correspond. Reformulez la description.")

    best_score = max(scores.values())
    candidates = [name for name, score in scores.items() if score == best_score]
    if len(candidates) == 1:
        return candidates[0]
    most_specific = [
        candidate
        for candidate in candidates
        if all(
            candidate == other or is_ancestor(other, candidate)
            for other in candidates
        )
    ]
    if len(most_specific) == 1:
        return most_specific[0]
    labels = ", ".join(display_name(name) for name in sorted(candidates)[:6])
    raise CreationError(f"Plusieurs classes correspondent : {labels}. Précisez la classe.")


def _longest_common_run(words: list[str], phrase: tuple[str, ...]) -> int:
    longest = 0
    for word_start in range(len(words)):
        for phrase_start in range(len(phrase)):
            width = 0
            while (
                word_start + width < len(words)
                and phrase_start + width < len(phrase)
                and words[word_start + width] == phrase[phrase_start + width]
            ):
                width += 1
            longest = max(longest, width)
    return longest


def _extract_property_values(description: str) -> dict[str, str]:
    known: dict[str, set[str]] = {}
    for item in list_properties():
        for form in (item.local_name, display_name(item.local_name)):
            key = normalized_question(form)
            known.setdefault(key, set()).add(item.local_name)

    values: dict[str, str] = {}
    consumed: list[tuple[int, int]] = []
    for match in _PROPERTY_ASSIGNMENT.finditer(description):
        raw_key = re.sub(r"^avec\s+", "", match.group("key").strip(), flags=re.IGNORECASE)
        key = normalized_question(raw_key)
        names = known.get(key, set())
        if len(names) != 1:
            label = raw_key
            raise CreationError(f"La propriété « {label} » n’est pas définie sans ambiguïté dans l’ontologie.")
        local_name = next(iter(names))
        if local_name in values:
            raise CreationError(f"La propriété « {display_name(local_name)} » est indiquée plusieurs fois.")
        value = match.group("value").strip().strip("«»\"'`").strip().rstrip(".?!")
        if not value:
            raise CreationError(f"Indiquez une valeur pour « {display_name(local_name)} ».")
        values[local_name] = value
        consumed.append(match.span())

    natural_matches: list[tuple[int, int, str, str]] = []
    aliases = _natural_property_patterns()
    for local_name, pattern in aliases:
        for match in pattern.finditer(description):
            if any(start <= match.start() < end for start, end in consumed):
                continue
            natural_matches.append((match.start(), match.end(), local_name, match.group()))
    natural_matches.sort(key=lambda item: (item[0], -(item[1] - item[0])))

    accepted: list[tuple[int, int, str, str]] = []
    for match in natural_matches:
        if accepted and match[0] < accepted[-1][1]:
            continue
        accepted.append(match)
    for index, (start, end, local_name, _phrase) in enumerate(accepted):
        if local_name in values:
            raise CreationError(f"La propriété « {display_name(local_name)} » est indiquée plusieurs fois.")
        next_start = accepted[index + 1][0] if index + 1 < len(accepted) else len(description)
        raw_value = description[end:next_start]
        raw_value = re.sub(r"^\s*(?:(?:est|de|:|=)\s*)+", "", raw_value, flags=re.IGNORECASE)
        raw_value = re.sub(r"^\s*(?:et|avec)\s+", "", raw_value, flags=re.IGNORECASE)
        raw_value = re.split(r"[,;.!?]", raw_value, maxsplit=1)[0].strip()
        if not raw_value:
            raise CreationError(f"Indiquez une valeur pour « {display_name(local_name)} ».")
        values[local_name] = raw_value.strip(" «»\"'`")
    return values


def _natural_property_patterns() -> list[tuple[str, re.Pattern[str]]]:
    patterns = []
    for local_name, phrases in _NATURAL_PROPERTY_ALIASES.items():
        for phrase in sorted(phrases, key=len, reverse=True):
            expression = r"(?<!\w)" + re.escape(phrase).replace(r"\ ", r"\s+") + r"(?!\w)"
            patterns.append((local_name, re.compile(expression, re.IGNORECASE)))
    return patterns


def _strip_natural_property_clauses(description: str) -> str:
    matches = sorted(
        (match for _name, pattern in _natural_property_patterns() for match in pattern.finditer(description)),
        key=lambda match: (match.start(), -(match.end() - match.start())),
    )
    selected = []
    for match in matches:
        if selected and match.start() < selected[-1].end():
            continue
        selected.append(match)

    spans: list[tuple[int, int]] = []
    for index, match in enumerate(selected):
        end = selected[index + 1].start() if index + 1 < len(selected) else len(description)
        delimiter = re.search(r"[,;.!?]|\bet\b", description[match.end():end], re.IGNORECASE)
        if delimiter:
            end = match.end() + delimiter.start()
        spans.append((match.start(), end))
    for start, end in reversed(spans):
        description = description[:start] + " " + description[end:]
    return description


def _infer_name(class_text: str, class_name: str) -> str:
    phrases = {
        display_name(class_name),
        class_name,
        *SUBJECTS.get("fr", {}).get(class_name, ()),
    }
    matches: list[re.Match[str]] = []
    for phrase in phrases:
        expression = re.escape(phrase).replace(r"\ ", r"\s+")
        match = re.search(r"(?<!\w)" + expression + r"(?!\w)", class_text, re.IGNORECASE)
        if match:
            matches.append(match)
    class_match = (
        min(matches, key=lambda match: (match.start(), -(match.end() - match.start())))
        if matches
        else None
    )
    if class_match is None:
        raise CreationError("Indiquez le nom de l’individu, par exemple « Ville Sfax ». ")

    tail = class_text[class_match.end():]
    tail = re.split(
        r"(?i)\b(?:avec|et|dans\s+(?:la\s+)?(?:r[eé]gion|zone|ville)|"
        r"r[eé]gion|puissance\s+install[eé]e|"
        r"situ[eé]\s+dans|localis[eé]\s+dans|se\s+trouve\s+dans)\b|[,;.!?]",
        tail,
        maxsplit=1,
    )[0]
    tail = re.sub(r"^\s*(?:de\s+type|de|du|des|une?|l['’])\s+", "", tail, flags=re.IGNORECASE)
    candidate = tail.strip()
    if not candidate:
        raise CreationError("Indiquez le nom de l’individu, par exemple « Ville Sfax ». ")
    return candidate


def _validate_domain(
    ontology_property: OntologyProperty,
    class_name: str,
) -> None:
    for domain_iri in ontology_property.domains:
        if not domain_iri.startswith(ONTOLOGY_NS):
            raise CreationError("Le domaine de cette propriété n’est pas une classe ENERGIE connue.")
        domain_name = domain_iri[len(ONTOLOGY_NS) :]
        if class_name != domain_name and not is_ancestor(domain_name, class_name):
            raise CreationError(
                f"La propriété « {display_name(ontology_property.local_name)} » "
                f"ne s’applique pas à la classe « {display_name(class_name)} »."
            )


def _literal_value(value: str, ranges: tuple[str, ...]) -> Literal:
    if len(ranges) != 1 or ranges[0] not in _DATATYPE_VALUES:
        raise CreationError("Le type de donnée de cette propriété n’est pas pris en charge.")
    datatype = ranges[0]
    try:
        if datatype == str(XSD.date):
            value = date.fromisoformat(value).isoformat()
        elif datatype == str(XSD.dateTime):
            value = datetime.fromisoformat(value).isoformat()
        elif datatype == str(XSD.integer):
            if not re.fullmatch(r"[+-]?\d+", value):
                raise ValueError
            value = str(int(value))
        elif datatype == str(XSD.decimal):
            decimal_value = Decimal(value)
            if not decimal_value.is_finite():
                raise ValueError
            value = format(decimal_value, "f")
        elif datatype == str(XSD.boolean):
            normalized = value.casefold()
            if normalized not in {"true", "false", "1", "0"}:
                raise ValueError
            value = {"1": "true", "0": "false"}.get(normalized, normalized)
    except (ValueError, InvalidOperation) as exc:
        raise CreationError("La valeur ne respecte pas le type de donnée de la propriété.") from exc
    return Literal(value, datatype=URIRef(datatype), normalize=False)


def _object_value_iri(
    value: str,
    ranges: tuple[str, ...],
    repository: IndividualRepository,
) -> str:
    if len(ranges) != 1 or not ranges[0].startswith(ONTOLOGY_NS):
        raise CreationError("La cible de cette propriété objet n’est pas une classe ENERGIE connue.")
    range_name = ranges[0][len(ONTOLOGY_NS) :]
    range_module = locate(range_name)
    if range_module is None:
        raise CreationError("La classe cible de cette propriété n’existe pas dans ENERGIE.rdf.")
    target_name = _local_name(value)
    target_iri = individual_iri(target_name)
    target = repository.get(range_module[0], target_name)
    if target is None or (target.class_name != range_name and not is_ancestor(range_name, target.class_name)):
        raise CreationError("La ressource indiquée n’existe pas avec le type attendu dans Fuseki.")
    return target_iri
