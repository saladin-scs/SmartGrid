"""Build and check read-only SPARQL for the NLP intents.

Templates interpolate only RDFLib serializations of IRIs and one namespace
literal. The user question is never copied into the query.
"""

from __future__ import annotations

import re

from rdflib import BNode, Literal, URIRef
from rdflib.plugins.sparql.algebra import translateQuery
from rdflib.plugins.sparql.parser import parseQuery
from rdflib.plugins.sparql.parserutils import CompValue
from rdflib.term import Variable

from web_sem.nlp.catalog import all_class_names, subtree_names
from web_sem.nlp.interpret import (
    COUNT_INDIVIDUALS,
    FILTER_BY_CLASS,
    GET_DETAILS,
    LIST_INDIVIDUALS,
    LIST_TYPES,
    Plan,
)
from web_sem.ontology import ONTOLOGY_NS, class_iri, individual_iri
from web_sem.sparql.service import _top_level_forms

RESULT_LIMIT = 100
_RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
_ALLOWED_NODES = frozenset(
    {
        "SelectQuery",
        "Slice",
        "Project",
        "OrderBy",
        "Filter",
        "Builtin_STRSTARTS",
        "Builtin_STR",
        "Builtin_LCASE",
        "Join",
        "ToMultiSet",
        "values",
        "BGP",
        "OrderCondition",
        "Extend",
        "AggregateJoin",
        "Aggregate_Count",
        "Group",
    }
)
_FORBIDDEN = re.compile(
    r"\b(?:INSERT|DELETE|LOAD|CLEAR|DROP|CREATE|COPY|MOVE|ADD|CONSTRUCT|DESCRIBE|ASK|SERVICE|PREFIX|GRAPH|FROM)\b",
    re.IGNORECASE,
)


class QueryRejected(Exception):
    """A query is not a supported read-only SELECT."""


def build_query(plan: Plan) -> str:
    if plan.intent in {LIST_INDIVIDUALS, FILTER_BY_CLASS}:
        return _select_individuals(subtree_names(plan.class_name))
    if plan.intent == COUNT_INDIVIDUALS:
        return _count_individuals(subtree_names(plan.class_name))
    if plan.intent == LIST_TYPES:
        return _select_classes(subtree_names(plan.class_name))
    if plan.intent == GET_DETAILS:
        return _select_details(plan.individual_name)
    raise QueryRejected("Unsupported intent.")


def validate_select(query: str) -> None:
    """Reject anything other than a bounded ontology SELECT."""
    if not isinstance(query, str) or not query.strip() or len(query) > 20000:
        raise QueryRejected("SPARQL query is empty or too large.")
    if _FORBIDDEN.search(query):
        raise QueryRejected("SPARQL query uses a forbidden operation.")
    if _top_level_forms(query) != ["SELECT"]:
        raise QueryRejected("Only a single SELECT query is accepted.")
    limits = [int(value) for value in re.findall(r"\bLIMIT\s+(\d+)\b", query)]
    if len(limits) != 1:
        raise QueryRejected("SPARQL query must declare one LIMIT.")

    try:
        algebra = translateQuery(parseQuery(query)).algebra
    except QueryRejected:
        raise
    except Exception as exc:
        raise QueryRejected("SPARQL query could not be parsed.") from exc

    scan = _Scan()
    _walk(algebra, scan)
    if scan.limit != limits[0] or not 1 <= scan.limit <= RESULT_LIMIT:
        raise QueryRejected("LIMIT is outside the allowed range.")
    if scan.ontology_iris < 1:
        raise QueryRejected("SPARQL query does not cite the ontology.")


def _select_individuals(local_names: list[str]) -> str:
    values = _class_values(local_names)
    namespace = _namespace_literal()
    return (
        "SELECT ?individual ?type\n"
        "WHERE {\n"
        f"  VALUES ?type {{ {values} }}\n"
        "  ?individual a ?type .\n"
        f"  FILTER(STRSTARTS(STR(?individual), {namespace}))\n"
        "}\n"
        "ORDER BY LCASE(STR(?individual))\n"
        f"LIMIT {RESULT_LIMIT}\n"
    )


def _count_individuals(local_names: list[str]) -> str:
    values = _class_values(local_names)
    namespace = _namespace_literal()
    return (
        "SELECT (COUNT(DISTINCT ?individual) AS ?count)\n"
        "WHERE {\n"
        f"  VALUES ?type {{ {values} }}\n"
        "  ?individual a ?type .\n"
        f"  FILTER(STRSTARTS(STR(?individual), {namespace}))\n"
        "}\n"
        "LIMIT 1\n"
    )


def _select_classes(local_names: list[str]) -> str:
    values = _class_values(local_names)
    return (
        "SELECT ?class\n"
        "WHERE {\n"
        f"  VALUES ?class {{ {values} }}\n"
        "}\n"
        "ORDER BY STR(?class)\n"
        f"LIMIT {RESULT_LIMIT}\n"
    )


def _select_details(local_name: str) -> str:
    individual = _individual_term(local_name)
    values = _class_values(all_class_names())
    namespace = _namespace_literal()
    return (
        "SELECT ?individual ?type\n"
        "WHERE {\n"
        f"  VALUES ?type {{ {values} }}\n"
        f"  BIND({individual} AS ?individual)\n"
        "  ?individual a ?type .\n"
        f"  FILTER(STRSTARTS(STR(?individual), {namespace}))\n"
        "}\n"
        f"LIMIT {RESULT_LIMIT}\n"
    )


def _class_values(local_names: list[str]) -> str:
    if not local_names:
        raise QueryRejected("The query has no ontology class.")
    return " ".join(_class_term(name) for name in local_names)


def _class_term(local_name: str) -> str:
    iri = class_iri(local_name)
    rendered = URIRef(iri).n3()
    if rendered != f"<{iri}>":
        raise QueryRejected("Class IRI could not be serialized safely.")
    return rendered


def _individual_term(local_name: str) -> str:
    iri = individual_iri(local_name)
    rendered = URIRef(iri).n3()
    if rendered != f"<{iri}>":
        raise QueryRejected("Individual IRI could not be serialized safely.")
    return rendered


def _namespace_literal() -> str:
    rendered = Literal(ONTOLOGY_NS).n3()
    if rendered != f'"{ONTOLOGY_NS}"':
        raise QueryRejected("Namespace literal could not be serialized safely.")
    return rendered


class _Scan:
    def __init__(self) -> None:
        self.ontology_iris = 0
        self.limit: int | None = None


def _walk(node: object, scan: _Scan) -> None:
    if isinstance(node, BNode):
        raise QueryRejected("Blank nodes are not allowed.")
    if isinstance(node, URIRef):
        iri = str(node)
        if iri == _RDF_TYPE:
            return
        if not iri.startswith(ONTOLOGY_NS):
            raise QueryRejected("Query IRI is outside the ontology namespace.")
        local_name = iri[len(ONTOLOGY_NS) :]
        try:
            class_iri(local_name)
        except ValueError as exc:
            raise QueryRejected("Query IRI is outside the ontology namespace.") from exc
        scan.ontology_iris += 1
        return
    if isinstance(node, Literal):
        if node.language or str(node) != ONTOLOGY_NS:
            raise QueryRejected("Query literal is not allowed.")
        return
    if isinstance(node, CompValue):
        if node.name not in _ALLOWED_NODES:
            raise QueryRejected(f"Unsupported SPARQL operator: {node.name}")
        if node.name == "SelectQuery" and node.get("datasetClause"):
            raise QueryRejected("Dataset clauses are not allowed.")
        if node.name == "Slice":
            start = node.get("start") or 0
            length = node.get("length")
            if (
                start != 0
                or isinstance(length, bool)
                or not isinstance(length, int)
                or not 1 <= length <= RESULT_LIMIT
            ):
                raise QueryRejected("LIMIT is outside the allowed range.")
            scan.limit = length
        for key, value in node.items():
            if key != "name":
                _walk(value, scan)
        return
    if isinstance(node, dict):
        for key, value in node.items():
            _walk(key, scan)
            _walk(value, scan)
        return
    if isinstance(node, (list, tuple, set, frozenset)):
        for item in node:
            _walk(item, scan)
        return
    if isinstance(node, (str, int, float, bool, type(None), Variable)):
        return
    raise QueryRejected(f"Unsupported SPARQL term: {type(node).__name__}")
