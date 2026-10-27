"""Run a natural-language question against Fuseki."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from urllib.parse import quote

from django.urls import reverse

from web_sem.nlp.catalog import locate, subtree_names
from web_sem.nlp.interpret import (
    COUNT_INDIVIDUALS,
    GET_DETAILS,
    GET_RELATIONS,
    LIST_TYPES,
    MAX_QUESTION,
    Plan,
    describe,
    interpret,
    say,
)
from web_sem.nlp.sparql import RESULT_LIMIT, QueryRejected, build_query, validate_select
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
        service = self._service if self._service is not None else SparqlService(timeout=NLP_TIMEOUT)
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

        try:
            return _present(text, plan, query, explanation, payload)
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
    if plan.intent == COUNT_INDIVIDUALS:
        count = _count(bindings)
    elif plan.intent == LIST_TYPES:
        rows = tuple(_class_rows(plan, bindings))
        if not rows:
            empty = say(plan.language, "empty_types")
    elif plan.intent == GET_DETAILS:
        rows = tuple(_individual_rows(bindings))
        if not rows:
            empty = say(plan.language, "empty_details", name=plan.individual_name)
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