"""Run a natural-language question against Fuseki."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, replace
from difflib import SequenceMatcher
from urllib.parse import quote

from django.urls import reverse

from web_sem.nlp.catalog import locate, subtree_names
from web_sem.nlp.interpret import (
    COUNT_BY_ZONE,
    COUNT_INDIVIDUALS,
    FILTER_BY_CLASS,
    GET_DETAILS,
    GET_RELATIONS,
    LIST_TYPES,
    MAX_QUESTION,
    ZONE_INTENTS,
    Plan,
    describe,
    interpret,
    say,
)
from web_sem.nlp.normalize import normalized_question
from web_sem.nlp.sparql import (
    RESULT_LIMIT,
    QueryRejected,
    build_individual_lookup,
    build_properties_query,
    build_query,
    build_zone_lookup,
    validate_select,
)
from web_sem.ontology import LOCAL_NAME_RE, MAX_LOCAL_NAME, ONTOLOGY_NS, display_name
from web_sem.sparql import SparqlService, SparqlServiceError

logger = logging.getLogger(__name__)

NLP_TIMEOUT = 10

SAMPLE_QUESTIONS = (
    "Quelles sources de production existent ?",
    "Liste les centrales nucléaires.",
    "Quels sont les moyens de stockage électrique ?",
    "Combien de sources de production existe-t-il ?",
    "Combien de centrales nucléaires existe-t-il ?",
    "Donne-moi les détails de CentraleTunis.",
    "Quels types de stockage sont disponibles ?",
    "Liste les consommateurs.",
    "Combien de consommateurs existe-t-il ?",
    "Affiche les détails de MaisonDemo.",
    "Liste les contrats.",
    "Combien de contrats existe-t-il ?",
    "Liste les contrats de type AbonnementResidentiel.",
    "Quels types de contrats sont disponibles ?",
    "Quels techniciens travaillent à Sfax ?",
    "Combien de personnes sont affectées à Tozeur ?",
    "Quels sites appartiennent à Tozeur ?",
    "Liste les opérateurs.",
    "Liste les villes.",
    "Quels contrats sont liés au client abonné ClientAbonne_LacTunis ?",
    "Quelles infrastructures sont situées dans la zone Ville_Sfax ?",
    "How many nuclear plants are there?",
)

_CLASS_LABEL = {
    "fr": ("Classe", "aucun individu", "individu(s)"),
    "en": ("Class", "no individual", "individual(s)"),
}


@dataclass(frozen=True, slots=True)
class ResultRow:
    title: str
    subtitle: str
    meta: str = ""
    href: str = ""


@dataclass(frozen=True, slots=True)
class Answer:
    question: str
    language: str = ""
    intent: str = ""
    sparql: str = ""
    explanation: str = ""
    clarification: str = ""
    error: str = ""
    rows: tuple[ResultRow, ...] = ()
    count: int | None = None
    empty_message: str = ""
    http_status: int = 200


class QuestionAnswering:
    """Normalize, interpret, validate, then SELECT through the shared Fuseki client."""

    def __init__(self, service=None) -> None:
        self._service = service

    def answer(self, question: str) -> Answer:
        text = " ".join(question.split()) if isinstance(question, str) else ""
        if len(text) > MAX_QUESTION:
            language = "fr" if any(char in text for char in "éèêëàâùûôîïç") else "en"
            return Answer(question=text[:MAX_QUESTION], language=language, clarification=say(language, "too_long"))
        plan = interpret(text)
        if plan.clarification:
            return Answer(question=text, language=plan.language, clarification=plan.clarification)

        service = self._service if self._service is not None else SparqlService(timeout=NLP_TIMEOUT)
        if plan.intent in ZONE_INTENTS:
            try:
                plan = _resolve_zone(plan, service)
            except SparqlServiceError:
                logger.exception("Fuseki could not list the zones")
                return Answer(
                    question=text,
                    language=plan.language,
                    intent=plan.intent,
                    error=say(plan.language, "store"),
                    http_status=503,
                )
            except (KeyError, TypeError, ValueError):
                logger.exception("Fuseki returned an unexpected zone list")
                return Answer(
                    question=text,
                    language=plan.language,
                    intent=plan.intent,
                    error=say(plan.language, "bad_result"),
                    http_status=502,
                )
            if plan.clarification:
                return Answer(question=text, language=plan.language, clarification=plan.clarification)

        try:
            query = build_query(plan)
            validate_select(query)
        except QueryRejected:
            logger.exception("Generated SPARQL failed the read-only policy")
            return Answer(
                question=text,
                language=plan.language,
                intent=plan.intent,
                error=say(plan.language, "policy"),
                http_status=500,
            )

        explanation = describe(plan, limit=RESULT_LIMIT)
        try:
            payload = service.select(query)
        except SparqlServiceError:
            logger.exception("Fuseki could not answer a natural-language question")
            return Answer(
                question=text,
                language=plan.language,
                intent=plan.intent,
                sparql=query,
                explanation=explanation,
                error=say(plan.language, "store"),
                http_status=503,
            )

        if (
            plan.intent == GET_RELATIONS
            and plan.relation == "zone_infrastructure"
            and not _has_individual_bindings(payload)
        ):
            try:
                fallback_plan = Plan(
                    language=plan.language,
                    intent=FILTER_BY_CLASS,
                    class_name="Infrastructure",
                )
                fallback_query = build_query(fallback_plan)
                validate_select(fallback_query)
                fallback_payload = service.select(fallback_query)
                matches = _infrastructures_named_for_zone(plan.entity_name, fallback_payload)
            except SparqlServiceError:
                logger.exception("Fuseki could not check infrastructure names against the requested zone")
                return Answer(
                    question=text,
                    language=plan.language,
                    intent=plan.intent,
                    sparql=query,
                    explanation=explanation,
                    error=say(plan.language, "store"),
                    http_status=503,
                )
            except (QueryRejected, KeyError, TypeError, ValueError):
                logger.exception("Fuseki returned an unexpected infrastructure lookup result")
                return Answer(
                    question=text,
                    language=plan.language,
                    intent=plan.intent,
                    sparql=query,
                    explanation=explanation,
                    error=say(plan.language, "bad_result"),
                    http_status=502,
                )
            if matches:
                payload = {"results": {"bindings": matches}}
                explanation += (
                    " Aucun lien RDF de localisation n’a été trouvé ; "
                    "les individus dont le nom contient celui de la zone sont affichés."
                    if plan.language == "fr"
                    else " No RDF location link was found; individuals whose names contain the zone name are shown."
                )

        if (
            plan.intent in {GET_DETAILS, GET_RELATIONS}
            and not (
                plan.intent == GET_RELATIONS
                and plan.relation == "zone_infrastructure"
            )
            and not _has_individual_bindings(payload)
        ):
            try:
                lookup_query = build_individual_lookup()
                validate_select(lookup_query)
                lookup_payload = service.select(lookup_query)
            except SparqlServiceError:
                logger.exception("Fuseki could not look up individuals for fuzzy name matching")
                return Answer(
                    question=text,
                    language=plan.language,
                    intent=plan.intent,
                    sparql=query,
                    explanation=explanation,
                    error=say(plan.language, "store"),
                    http_status=503,
                )
            except (QueryRejected, KeyError, TypeError, ValueError):
                logger.exception("Fuseki returned an unexpected individual lookup result")
                return Answer(
                    question=text,
                    language=plan.language,
                    intent=plan.intent,
                    sparql=query,
                    explanation=explanation,
                    error=say(plan.language, "bad_result"),
                    http_status=502,
                )

            try:
                matches = _fuzzy_individual_matches(_requested_individual(plan), lookup_payload)
            except (KeyError, TypeError, ValueError):
                logger.exception("Fuseki returned an unexpected individual lookup result")
                return Answer(
                    question=text,
                    language=plan.language,
                    intent=plan.intent,
                    sparql=query,
                    explanation=explanation,
                    error=say(plan.language, "bad_result"),
                    http_status=502,
                )
            if len(matches) > 1:
                clarification = say(
                    plan.language,
                    "individual_several",
                    name=_requested_individual(plan),
                    names=", ".join(matches[:6]),
                )
                return Answer(
                    question=text,
                    language=plan.language,
                    intent=plan.intent,
                    clarification=clarification,
                )
            if matches and matches[0] != _requested_individual(plan):
                plan = (
                    replace(plan, individual_name=matches[0])
                    if plan.intent == GET_DETAILS
                    else replace(plan, entity_name=matches[0])
                )
                try:
                    query = build_query(plan)
                    validate_select(query)
                    explanation = describe(plan, limit=RESULT_LIMIT)
                    payload = service.select(query)
                except QueryRejected:
                    logger.exception("Generated fuzzy individual query failed the read-only policy")
                    return Answer(
                        question=text,
                        language=plan.language,
                        intent=plan.intent,
                        error=say(plan.language, "policy"),
                        http_status=500,
                    )
                except SparqlServiceError:
                    logger.exception("Fuseki could not retrieve the fuzzy-matched individual")
                    return Answer(
                        question=text,
                        language=plan.language,
                        intent=plan.intent,
                        sparql=query,
                        explanation=explanation,
                        error=say(plan.language, "store"),
                        http_status=503,
                    )

        try:
            answer = _present(text, plan, query, explanation, payload)
            if plan.intent == GET_DETAILS and answer.rows:
                answer = replace(answer, rows=answer.rows + _property_rows(plan, service))
            return answer
        except (KeyError, TypeError, ValueError):
            logger.exception("Fuseki returned an unexpected NLP result")
            return Answer(
                question=text,
                language=plan.language,
                intent=plan.intent,
                sparql=query,
                explanation=explanation,
                error=say(plan.language, "bad_result"),
                http_status=502,
            )


def answer_question(question: str, *, service=None) -> Answer:
    return QuestionAnswering(service).answer(question)


def _present(question: str, plan: Plan, query: str, explanation: str, payload: dict) -> Answer:
    results = payload.get("results") if isinstance(payload, dict) else None
    bindings = results.get("bindings") if isinstance(results, dict) else None
    if not isinstance(bindings, list):
        raise TypeError("SPARQL JSON bindings are missing.")

    count = None
    rows: tuple[ResultRow, ...] = ()
    empty = ""
    if plan.intent in {COUNT_INDIVIDUALS, COUNT_BY_ZONE}:
        count = _count(bindings)
    elif plan.intent == LIST_TYPES:
        rows = tuple(_class_rows(plan, bindings))
        if not rows:
            empty = say(plan.language, "empty_types")
    elif plan.intent == GET_DETAILS:
        rows = tuple(_individual_rows(bindings))
        if not rows:
            empty = say(plan.language, "empty_details", name=plan.individual_name)
    elif plan.intent in ZONE_INTENTS:
        rows = tuple(_individual_rows(bindings))
        if not rows:
            empty = say(
                plan.language, "empty_by_zone", name=display_name(plan.class_name), zone=plan.zone_name
            )
    elif plan.intent == GET_RELATIONS:
        rows = tuple(_individual_rows(bindings))
        if not rows:
            empty = say(plan.language, "empty_related", name=plan.entity_name)
    else:  # LIST_INDIVIDUALS, FILTER_BY_CLASS: classes first, then individuals
        rows = tuple(_list_rows(plan, bindings)) + tuple(_individual_rows(bindings))
        if not rows:
            empty = say(plan.language, "empty_list", name=display_name(plan.class_name))

    return Answer(
        question=question,
        language=plan.language,
        intent=plan.intent,
        sparql=query,
        explanation=explanation,
        rows=rows,
        count=count,
        empty_message=empty,
    )


def _resolve_zone(plan: Plan, service) -> Plan:
    """Turn the words after "à" into the local name of one Zone individual.

    Zones come from Fuseki (local name and nomZone). The question's text is only
    compared to them here, it is never put in a query.
    """
    query = build_zone_lookup()
    validate_select(query)
    payload = service.select(query)
    wanted = frozenset(normalized_question(plan.zone_text).split()) - _FILLER
    candidates: dict[str, list[frozenset[str]]] = {}
    for binding in payload["results"]["bindings"]:
        name = _local(_value(binding, "zone"))
        if not name:
            continue
        spellings = candidates.setdefault(name, [])
        for text in (name, _value(binding, "nom")):
            words = frozenset(normalized_question(text).split()) - _FILLER
            if words:
                spellings.append(words)

    # A zone is known by its local name and by its nomZone. The whole phrase must
    # equal one of them ("Sfax" = Ville_Sfax); failing that, the phrase may be a
    # part of a longer name ("Sfax" in "Stockage de Sfax").
    exact = [name for name, spellings in candidates.items() if wanted in spellings]
    partial = [
        name for name, spellings in candidates.items() if any(wanted and wanted <= words for words in spellings)
    ]
    found = exact or sorted(partial)
    if not found:
        return replace(plan, clarification=say(plan.language, "zone_unknown", zone=plan.zone_text))
    if len(found) > 1:
        return replace(
            plan,
            clarification=say(plan.language, "zone_several", zone=plan.zone_text, names=", ".join(found[:6])),
        )
    return replace(plan, zone_name=found[0])


_FILLER = frozenset({"de", "du", "des", "la", "le", "les", "l", "d", "ville", "zone", "region", "site"})


def _has_individual_bindings(payload: object) -> bool:
    if not isinstance(payload, dict):
        return False
    results = payload.get("results")
    if not isinstance(results, dict):
        return False
    bindings = results.get("bindings")
    return isinstance(bindings, list) and bool(bindings)


def _requested_individual(plan: Plan) -> str:
    return plan.individual_name if plan.intent == GET_DETAILS else plan.entity_name


def _infrastructures_named_for_zone(zone_name: str, payload: object) -> list[dict]:
    if not isinstance(payload, dict):
        raise TypeError("Infrastructure lookup response is not an object.")
    results = payload.get("results")
    if not isinstance(results, dict) or not isinstance(results.get("bindings"), list):
        raise TypeError("Infrastructure lookup bindings are missing.")

    zone_key = _individual_key(zone_name)
    if not zone_key:
        return []
    return [
        binding
        for binding in results["bindings"]
        if isinstance(binding, dict)
        and (individual_name := _local(_value(binding, "individual")))
        and zone_key in _individual_key(individual_name)
    ]


def _fuzzy_individual_matches(wanted: str, payload: object) -> list[str]:
    if not isinstance(payload, dict):
        raise TypeError("Individual lookup response is not an object.")
    results = payload.get("results")
    if not isinstance(results, dict) or not isinstance(results.get("bindings"), list):
        raise TypeError("Individual lookup bindings are missing.")

    candidates = {
        local_name
        for binding in results["bindings"]
        if (local_name := _local(_value(binding, "individual")))
    }
    wanted_key = _individual_key(wanted)
    if len(wanted_key) < 4:
        return []

    scored = sorted(
        (
            (SequenceMatcher(None, wanted_key, _individual_key(name)).ratio(), name)
            for name in candidates
            if len(_individual_key(name)) >= 4
        ),
        reverse=True,
    )
    if not scored or scored[0][0] < 0.78:
        return []
    best = scored[0][0]
    return sorted(name for score, name in scored if best - score <= 0.04)


def _individual_key(value: str) -> str:
    separated = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", value.replace("_", " "))
    return "".join(normalized_question(separated).split())


def _property_rows(plan: Plan, service) -> tuple[ResultRow, ...]:
    """Name, matricule, links... of the individual; best effort, details still work without."""
    try:
        query = build_properties_query(plan.individual_name)
        validate_select(query)
        payload = service.select(query)
        rows = []
        for binding in payload["results"]["bindings"]:
            name = _local(_value(binding, "property"))
            raw = _value(binding, "value")
            if not name or not raw:
                continue
            value = _local(raw) or raw
            rows.append(ResultRow(title=name, subtitle=value, meta="propriété"))
        return tuple(rows)
    except (SparqlServiceError, QueryRejected, KeyError, TypeError, ValueError):
        logger.exception("Could not read the properties of %s", plan.individual_name)
        return ()


def _count(bindings: list) -> int:
    if len(bindings) != 1:
        raise ValueError("COUNT did not return one row.")
    raw = _value(bindings[0], "count")
    if not raw.isdigit():
        raise ValueError("COUNT was not an integer.")
    return int(raw)


def _list_rows(plan: Plan, bindings: list) -> list[ResultRow]:
    """One row per class of the subtree, with its number of individuals.

    The query uses OPTIONAL, so a class with no individual still comes back
    with ?type bound and ?individual unbound.
    """
    members: dict[str, set[str]] = {}
    for binding in bindings:
        type_name = _local(_value(binding, "type"))
        if not type_name:
            continue
        found = members.setdefault(type_name, set())
        individual = _local(_value(binding, "individual"))
        if individual:
            found.add(individual)

    label, none, unit = _CLASS_LABEL.get(plan.language, _CLASS_LABEL["en"])
    rows: list[ResultRow] = []
    for local_name in subtree_names(plan.class_name):
        if local_name not in members:
            continue
        located = locate(local_name)
        if located is None:
            continue
        module, ontology_class = located
        total = len(members[local_name])
        detail = none if total == 0 else f"{total} {unit}"
        rows.append(
            ResultRow(
                title=ontology_class.display_name,
                subtitle=f"{label} · {detail}",
                meta=" / ".join(module.hierarchy(local_name)),
                href=f"{reverse(module.list_url_name)}?rdf_type={quote(local_name)}",
            )
        )
    return rows


def _individual_rows(bindings: list) -> list[ResultRow]:
    grouped: dict[str, list[str]] = {}
    for binding in bindings:
        local_name = _local(_value(binding, "individual"))
        type_name = _local(_value(binding, "type"))
        if not local_name or not type_name:
            continue
        grouped.setdefault(local_name, []).append(type_name)

    rows: list[ResultRow] = []
    for local_name, type_names in grouped.items():
        ranked = [found for name in type_names if (found := locate(name)) is not None]
        if not ranked:
            continue
        module, ontology_class = max(ranked, key=lambda item: item[1].depth)
        rows.append(
            ResultRow(
                title=local_name,
                subtitle=ontology_class.display_name,
                meta=" / ".join(module.hierarchy(ontology_class.local_name)),
                href=reverse(module.detail_url_name, args=[local_name]),
            )
        )
    return rows


def _class_rows(plan: Plan, bindings: list) -> list[ResultRow]:
    returned = {_local(_value(binding, "class")) for binding in bindings}
    returned.discard("")
    rows: list[ResultRow] = []
    for local_name in subtree_names(plan.class_name):
        if local_name not in returned:
            continue
        found = locate(local_name)
        if found is None:
            continue
        module, ontology_class = found
        parent = display_name(ontology_class.parent) if ontology_class.parent else ""
        rows.append(
            ResultRow(
                title=ontology_class.display_name,
                subtitle=parent,
                meta=local_name,
                href=f"{reverse(module.list_url_name)}?rdf_type={quote(local_name)}",
            )
        )
    return rows


def _value(binding: object, name: str) -> str:
    if not isinstance(binding, dict):
        return ""
    term = binding.get(name) or {}
    if not isinstance(term, dict):
        return ""
    value = term.get("value", "")
    return value if isinstance(value, str) else ""


def _local(iri: str) -> str:
    if not iri.startswith(ONTOLOGY_NS):
        return ""
    local_name = iri[len(ONTOLOGY_NS) :]
    if not LOCAL_NAME_RE.fullmatch(local_name) or len(local_name) > MAX_LOCAL_NAME:
        return ""
    return local_name