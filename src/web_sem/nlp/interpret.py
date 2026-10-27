"""Intent detection for SourceProduction and Stockage questions.

Unsupported or ambiguous questions become a clarification. They do not pick a
nearby class.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from web_sem.nlp.aliases import Alias, alias_index, cue_index
from web_sem.nlp.catalog import (
    all_class_names,
    is_ancestor,
    is_root,
    locate,
    relation_properties,
    subtree_names,
)
from web_sem.nlp.normalize import _CLITICS, find_phrases, normalized_question
from web_sem.ontology import (
    LOCAL_NAME_RE,
    MAX_LOCAL_NAME,
    ONTOLOGY_NS,
    display_name,
    reserved_names,
)

LIST_INDIVIDUALS = "LIST_INDIVIDUALS"
FILTER_BY_CLASS = "FILTER_BY_CLASS"
GET_DETAILS = "GET_DETAILS"
COUNT_INDIVIDUALS = "COUNT_INDIVIDUALS"
LIST_TYPES = "LIST_TYPES"
LIST_BY_ZONE = "LIST_BY_ZONE"
COUNT_BY_ZONE = "COUNT_BY_ZONE"
ZONE_INTENTS = frozenset({LIST_BY_ZONE, COUNT_BY_ZONE})

MAX_QUESTION = 400
_STRONG = ("count", "types", "details")
_ARTICLES = frozenset({"le", "la", "les", "un", "une", "des", "du", "de", "d", "the", "a", "an", "of"})
_INJECTION_RE = re.compile(
    r"[{};\\]|/\*|\*/|--|"
    r"\b(?:INSERT|DELETE|LOAD|CLEAR|DROP|CONSTRUCT|DESCRIBE|SELECT|PREFIX|SERVICE|GRAPH)\b",
    re.IGNORECASE,
)
_DETAIL_RE = re.compile(
    r"(?is)\b(?:d[eé]tails?|fiche|informations?|details?)\s+"
    r"(?:(?:de|du|des|d['’]|of|for|about|sur)\s+)?(\S.*?)\s*$"
)
# "... à Sfax", "... dans la ville de Tozeur": the words after the preposition name a zone.
_ZONE_RE = re.compile(
    r"(?is)\b(?:à|au|aux|dans|en)\s+(?:(?:la|le|les|l['’])\s*)?(\S.*?)\s*[?.!]*\s*$"
)
_CLASS_FILTER_RE = re.compile(r"(?is)\b(?:de\s+type|type)\s+([A-Za-z][A-Za-z0-9_]*)\s*[.?!]*\s*$")

_TEXT: dict[str, dict[str, str]] = {
    "fr": {
        "injection": "Cette question contient une syntaxe SPARQL. Reformulez-la en langage naturel.",
        "empty": "Saisissez une question sur la production, le stockage, les consommateurs, les contrats, les personnes ou les zones.",
        "unsupported": (
            "Je ne reconnais pas cette question pour les sources de production, le stockage, "
            "les consommateurs, les contrats, les personnes ou les zones. "
            "Par exemple : « Quelles sources de production existent ? » "
            "ou « Quels techniciens travaillent à Sfax ? »."
        ),
        "several": "Plusieurs classes correspondent : {names}. Précisez une seule classe.",
        "mixed": "La question mélange plusieurs demandes. Choisissez une liste, un compte, un détail ou les types.",
        "class_name": (
            "{name} est une classe de l'ontologie, pas un individu. "
            "Demandez une liste, un compte ou les types."
        ),
        "reserved": "{name} est un terme de l'ontologie, pas un individu pris en charge.",
        "bad_name": (
            "Le détail attend un nom local exact, par exemple CentraleTunis, "
            "ou un IRI de l'ontologie ENERGIE."
        ),
        "which_class": "Précisez une classe existante dans ENERGIE.rdf.",
        "too_long": "La question est trop longue.",
        "store": "Le serveur RDF n'a pas pu exécuter cette requête.",
        "policy": "La requête générée a été refusée avant d'atteindre Fuseki.",
        "bad_result": "La réponse du serveur RDF est incomplète.",
        "empty_list": "Aucun individu de la classe {name} n'est dans le jeu de données energy.",
        "empty_details": (
            "Aucun individu nommé {name} n'a de type pris en charge "
            "dans le jeu de données."
        ),
        "empty_types": "La requête n'a retourné aucune classe.",
        "zone_unknown": "Je ne trouve aucune zone nommée « {zone} » dans le jeu de données.",
        "zone_several": "Plusieurs zones correspondent à « {zone} » : {names}. Précisez le nom.",
        "by_zone": (
            "Individus de type {name} ou de ses sous-classes reliés à la zone {zone} "
            "par {properties}. Au plus {limit} lignes."
        ),
        "count_by_zone": "Nombre d'individus de type {name} (sous-classes comprises) reliés à la zone {zone}.",
        "empty_by_zone": "Aucun individu de type {name} n'est relié à la zone {zone}.",
        "list_leaf": "Individus dont le type asserté est {name}.",
        "list_tree": (
            "Individus dont le type asserté est {name} ou l'une de ses {count} sous-classes. "
            "Fuseki ne matérialise pas les types inférés : VALUES cite chaque classe. "
            "Au plus {limit} lignes."
        ),
        "count_leaf": "Nombre d'individus dont le type asserté est {name}.",
        "count_tree": (
            "Nombre d'individus dont le type asserté est {name} ou l'une de ses {count} sous-classes. "
            "Chaque classe est citée dans VALUES."
        ),
        "details": "Types RDF assertés pour l'individu {name}.",
        "types": "Classes sous {name} déclarées dans ENERGIE.rdf. La requête SELECT retourne ces IRIs.",
    },
    "en": {
        "injection": "That question contains SPARQL syntax. Ask it in natural language.",
        "empty": "Enter a question about production, storage, consumers, or contracts.",
        "unsupported": (
            "I can't match that question to production sources, storage, consumers, or contracts. "
            'For example: "Which production sources exist?"'
        ),
        "several": "Several classes match: {names}. Name one class.",
        "mixed": "The question mixes several requests. Ask for a list, a count, a detail, or the types.",
        "class_name": (
            "{name} is an ontology class, not an individual. "
            "Ask for a list, a count, or the available types."
        ),
        "reserved": "{name} is an ontology term, not a supported individual.",
        "bad_name": "Details need an exact local name such as CentraleTunis, or an IRI in the ENERGIE ontology.",
        "which_class": "Name a class that exists in ENERGIE.rdf.",
        "too_long": "The question is too long.",
        "store": "The RDF store could not run this query.",
        "policy": "The generated query was rejected before it reached Fuseki.",
        "bad_result": "The RDF store returned an unexpected result.",
        "empty_list": "No individual of {name} is in the energy dataset.",
        "empty_details": "No individual named {name} has a supported type in the dataset.",
        "empty_types": "The query returned no classes.",
        "zone_unknown": "I can't find a zone named \"{zone}\" in the dataset.",
        "zone_several": "Several zones match \"{zone}\": {names}. Give the exact name.",
        "by_zone": (
            "Individuals of type {name} (or subclasses) linked to the zone {zone} "
            "through {properties}. At most {limit} rows."
        ),
        "count_by_zone": "Number of individuals of type {name} (including subclasses) linked to the zone {zone}.",
        "empty_by_zone": "No individual of type {name} is linked to the zone {zone}.",
        "list_leaf": "Individuals whose asserted type is {name}.",
        "list_tree": (
            "Individuals whose asserted type is {name} or one of its {count} subclasses. "
            "Inferred types are not assumed to be stored in Fuseki: VALUES lists every class. "
            "At most {limit} rows."
        ),
        "count_leaf": "Number of individuals whose asserted type is {name}.",
        "count_tree": (
            "Number of individuals whose asserted type is {name} or one of its {count} subclasses. "
            "Every class is cited in VALUES."
        ),
        "details": "Asserted RDF types for the individual {name}.",
        "types": "Classes under {name} declared in ENERGIE.rdf. The SELECT query returns those IRIs.",
    },
}


@dataclass(frozen=True, slots=True)
class Plan:
    language: str
    intent: str = ""
    class_name: str = ""
    individual_name: str = ""
    clarification: str = ""
    zone_text: str = ""  # words after "à" in the question, still to be resolved
    zone_name: str = ""  # local name of the Zone individual once resolved


def say(language: str, key: str, **values: object) -> str:
    table = _TEXT.get(language) or _TEXT["en"]
    return table[key].format(**values)


def interpret(question: str) -> Plan:
    """Map one question to an intent, or to a clarification."""
    language = _language(question, {}, [])
    if len(question) > MAX_QUESTION:
        return Plan(language, clarification=say(language, "too_long"))
    if _INJECTION_RE.search(question):
        return Plan(language, clarification=say(language, "injection"))

    normalized = normalized_question(question)
    if not normalized:
        return Plan(language, clarification=say(language, "empty"))

    hits = _classes(normalized)
    if not hits:
        hits = _fallback_classes(normalized)
    cues = _cues(normalized)
    language = _language(question, cues, hits)
    strong = [kind for kind in _STRONG if cues.get(kind)]
    if len(strong) > 1:
        return Plan(language, clarification=say(language, "mixed"))
    class_filter = _CLASS_FILTER_RE.search(question)
    if class_filter:
        requested_class = _exact_class(class_filter.group(1))
        if requested_class is None:
            return Plan(language, clarification=say(language, "which_class"))
        target = locate(requested_class)
        roots = [hit for hit in hits if is_root(hit.local_name)]
        root_modules = {locate(hit.local_name)[0].root for hit in roots}
        if target is None or (root_modules and root_modules != {target[0].root}):
            return Plan(language, clarification=say(language, "which_class"))
        if cues.get("list") or not strong:
            return Plan(language, FILTER_BY_CLASS, requested_class)

    if "details" in strong or _DETAIL_RE.search(question):
        if strong and strong != ["details"]:
            return Plan(language, clarification=say(language, "mixed"))
        return _details(question, language)

    zone_plan = _zone_plan(question, language, hits, strong)
    if zone_plan is not None:
        return zone_plan

    if len(hits) > 1:
        names = ", ".join(display_name(hit.local_name) for hit in hits[:6])
        return Plan(language, clarification=say(language, "several", names=names))

    if "types" in strong:
        if not hits:
            return Plan(language, clarification=say(language, "which_class"))
        return Plan(language, LIST_TYPES, hits[0].local_name)

    if "count" in strong:
        if not hits:
            return Plan(language, clarification=say(language, "which_class"))
        return Plan(language, COUNT_INDIVIDUALS, hits[0].local_name)

    if not hits:
        return Plan(language, clarification=say(language, "unsupported"))
    if is_root(hits[0].local_name):
        return Plan(language, LIST_INDIVIDUALS, hits[0].local_name)
    return Plan(language, FILTER_BY_CLASS, hits[0].local_name)


def describe(plan: Plan, *, limit: int) -> str:
    """Explain a plan in the language detected for the question."""
    if plan.intent == GET_DETAILS:
        return say(plan.language, "details", name=plan.individual_name)
    label = display_name(plan.class_name)
    if plan.intent in ZONE_INTENTS:
        key = "count_by_zone" if plan.intent == COUNT_BY_ZONE else "by_zone"
        return say(
            plan.language,
            key,
            name=label,
            zone=plan.zone_name,
            properties=", ".join(relation_properties(plan.class_name)),
            limit=limit,
        )
    if plan.intent == LIST_TYPES:
        return say(plan.language, "types", name=label)
    subclasses = max(len(subtree_names(plan.class_name)) - 1, 0)
    if plan.intent == COUNT_INDIVIDUALS:
        key = "count_leaf" if subclasses == 0 else "count_tree"
        return say(plan.language, key, name=label, count=subclasses)
    key = "list_leaf" if subclasses == 0 else "list_tree"
    return say(plan.language, key, name=label, count=subclasses, limit=limit)


def _zone_plan(question: str, language: str, hits: list[Alias], strong: list[str]) -> Plan | None:
    """A question such as "Quels techniciens travaillent à Sfax ?".

    One class that can be linked to a zone, plus the words after "à/dans".
    The zone name is resolved later against the zones stored in Fuseki, so the
    text of the question never goes into the SPARQL query.
    """
    if not hits or set(strong) - {"count"}:
        return None
    match = _ZONE_RE.search(question)
    if match is None:
        return None
    zone_text = _clean_candidate(match.group(1))
    if not zone_text or len(zone_text) > MAX_LOCAL_NAME:
        return None
    # The class is whatever comes before "à": "Parc solaire de Tozeur" is a zone name,
    # not a second class in the question.
    head = _classes(normalized_question(question[: match.start()]))
    if len(head) != 1 or not relation_properties(head[0].local_name):
        return None
    intent = COUNT_BY_ZONE if "count" in strong else LIST_BY_ZONE
    return Plan(language, intent, head[0].local_name, zone_text=zone_text)


def _details(question: str, language: str) -> Plan:
    match = _DETAIL_RE.search(question)
    if match is None:
        return Plan(language, clarification=say(language, "bad_name"))
    candidate = _clean_candidate(match.group(1))
    local_name = _individual_name(candidate)
    if local_name:
        if local_name in reserved_names():
            key = "class_name" if locate(local_name) else "reserved"
            return Plan(language, clarification=say(language, key, name=display_name(local_name)))
        return Plan(language, GET_DETAILS, individual_name=local_name)
    class_name = _exact_class(candidate)
    if class_name:
        return Plan(language, clarification=say(language, "class_name", name=display_name(class_name)))
    return Plan(language, clarification=say(language, "bad_name"))


def _classes(normalized: str) -> list[Alias]:
    phrases = [(alias.phrase, alias) for alias in alias_index()]
    hits = find_phrases(normalized, phrases)
    names = {hit.local_name for hit in hits}
    kept: list[Alias] = []
    seen: set[str] = set()
    for hit in hits:
        if hit.local_name in seen:
            continue
        if any(is_ancestor(hit.local_name, other) for other in names if other != hit.local_name):
            continue
        # "site solaire" also contains "solaire": the longer phrase wins.
        if any(
            other.local_name != hit.local_name and f" {hit.phrase} " in f" {other.phrase} "
            for other in hits
        ):
            continue
        seen.add(hit.local_name)
        kept.append(hit)
    return kept


def _fallback_classes(normalized: str) -> list[Alias]:
    """Match individual content words against ontology class names.

    Used when no controlled alias phrase matches the question exactly.
    Returns aliases whose normalized phrase matches any word in the question.
    """
    words = [w for w in normalized.split() if w and w not in _CLITICS and w not in _ARTICLES]
    if not words:
        return []
    aliases = alias_index()
    hits: list[Alias] = []
    seen: set[str] = set()
    for word in words:
        for alias in aliases:
            if alias.local_name in seen:
                continue
            if alias.phrase == word or word in alias.phrase.split():
                hits.append(alias)
                seen.add(alias.local_name)
    return hits


def _cues(normalized: str) -> dict[str, set[str]]:
    found: dict[str, set[str]] = {kind: set() for kind in ("count", "types", "details", "list")}
    phrases = [(cue.phrase, cue) for cue in cue_index()]
    for cue in find_phrases(normalized, phrases):
        found[cue.kind].add(cue.language)
    return found


def _language(question: str, cues: dict[str, set[str]], hits: list[Alias]) -> str:
    scores = {"fr": 0, "en": 0}
    for kind, languages in cues.items():
        weight = 1 if kind == "list" else 2
        for language in languages:
            scores[language] = scores.get(language, 0) + weight
    for hit in hits:
        scores[hit.language] = scores.get(hit.language, 0) + 2
    if scores["fr"] > scores["en"]:
        return "fr"
    if scores["en"] > scores["fr"]:
        return "en"
    if scores["fr"] or _has_accent(question):
        return "fr"
    return "en"


def _has_accent(text: str) -> bool:
    decomposed = unicodedata.normalize("NFKD", text)
    return any(unicodedata.combining(char) for char in decomposed)


def _clean_candidate(fragment: str) -> str:
    text = fragment.strip().strip("«»\"'`").strip()
    text = re.sub(r"[.?!]+$", "", text).strip()
    if text.startswith("<") and text.endswith(">"):
        text = text[1:-1].strip()
    return text


def _individual_name(candidate: str) -> str | None:
    if any(char.isspace() for char in candidate):
        return None
    if LOCAL_NAME_RE.fullmatch(candidate) and len(candidate) <= MAX_LOCAL_NAME:
        return candidate
    if candidate.startswith(ONTOLOGY_NS):
        local_name = candidate[len(ONTOLOGY_NS) :]
        if LOCAL_NAME_RE.fullmatch(local_name) and len(local_name) <= MAX_LOCAL_NAME:
            return local_name
    return None


def _exact_class(candidate: str) -> str | None:
    parts = normalized_question(candidate).split()
    while parts and parts[0] in _ARTICLES:
        parts.pop(0)
    key = " ".join(parts)
    if not key:
        return None
    for alias in alias_index():
        if alias.phrase == key:
            return alias.local_name
    return None
