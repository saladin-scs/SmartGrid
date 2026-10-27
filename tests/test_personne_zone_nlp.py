"""French questions about Personne and Zone, answered from ENERGIE.rdf in memory."""

from __future__ import annotations

import pytest
from rdflib import Graph

from web_sem.nlp.interpret import (
    COUNT_BY_ZONE,
    COUNT_INDIVIDUALS,
    FILTER_BY_CLASS,
    GET_DETAILS,
    LIST_BY_ZONE,
    interpret,
)
from web_sem.nlp.service import answer_question
from web_sem.nlp.sparql import QueryRejected, build_query, validate_select


class GraphService:
    """Stands in for Fuseki: same select() contract, backed by the ontology file."""

    def __init__(self) -> None:
        self.graph = Graph().parse("data/ontology/ENERGIE.rdf")
        self.queries: list[str] = []

    def select(self, query: str) -> dict:
        self.queries.append(query)
        result = self.graph.query(query)
        bindings = []
        for row in result:
            binding = {}
            for var in result.vars:
                value = row[var]
                if value is not None:
                    kind = "uri" if str(value).startswith("http") else "literal"
                    binding[str(var)] = {"type": kind, "value": str(value)}
            bindings.append(binding)
        return {"results": {"bindings": bindings}}


def _titles(answer) -> set[str]:
    return {row.title for row in answer.rows}


@pytest.mark.parametrize(
    ("question", "intent", "class_name"),
    [
        ("Liste les techniciens.", FILTER_BY_CLASS, "Technicien"),
        ("Combien de techniciens de ligne existe-t-il ?", COUNT_INDIVIDUALS, "TechnicienLigne"),
        ("Quels sont les sites solaires ?", FILTER_BY_CLASS, "SiteSolaire"),
        ("Liste les villes.", FILTER_BY_CLASS, "Ville"),
        ("Liste les opérateurs.", FILTER_BY_CLASS, "Operateur"),
        ("Quels techniciens travaillent à Sfax ?", LIST_BY_ZONE, "Technicien"),
        ("Combien de personnes sont affectées à Tozeur ?", COUNT_BY_ZONE, "Personne"),
        ("Quels sites appartiennent à Tozeur ?", LIST_BY_ZONE, "SiteInstallation"),
    ],
)
def test_questions_are_understood(question, intent, class_name):
    plan = interpret(question)
    assert (plan.intent, plan.class_name) == (intent, class_name)


def test_technicians_of_a_zone_do_not_include_other_zones():
    answer = answer_question("Quels techniciens travaillent à Sfax ?", service=GraphService())
    assert _titles(answer) == {"TechnicienLigne_Sami"}
    assert "estAffecteA" in answer.sparql and "Ville_Sfax" in answer.sparql


def test_count_people_in_a_zone():
    answer = answer_question("Combien de personnes sont affectées à Tozeur ?", service=GraphService())
    assert answer.count == 1  # TechnicienPoste_Rim; the operator works at the solar site


def test_clients_are_counted_through_residentDans():
    answer = answer_question("Combien de clients abonnés à Sfax ?", service=GraphService())
    assert answer.count == 1
    assert "residentDans" in answer.sparql


def test_sites_of_a_city():
    answer = answer_question("Quels sites appartiennent à Tozeur ?", service=GraphService())
    assert _titles(answer) == {"SiteSolaire_Tozeur"}
    assert "appartientAVille" in answer.sparql


def test_zone_can_be_named_by_its_nomZone():
    answer = answer_question("Quels opérateurs travaillent au Parc solaire de Tozeur ?", service=GraphService())
    assert _titles(answer) == {"Operateur_Karim"}


def test_unknown_zone_is_a_clarification_not_a_wrong_answer():
    answer = answer_question("Quels techniciens travaillent à Narnia ?", service=GraphService())
    assert "Narnia" in answer.clarification
    assert not answer.rows and answer.count is None


def test_empty_result_has_a_message():
    answer = answer_question("Quels ingénieurs travaillent à Tozeur ?", service=GraphService())
    assert not answer.rows and answer.empty_message


def test_details_show_the_properties():
    answer = answer_question("Donne-moi les détails de Ingenieur_Amal.", service=GraphService())
    assert answer.intent == GET_DETAILS
    shown = {(row.title, row.subtitle) for row in answer.rows}
    assert ("nomPersonne", "Amal") in shown
    assert ("matricule", "ING-001") in shown
    assert ("estAffecteA", "Ville_Sfax") in shown


@pytest.mark.parametrize(
    "question",
    [
        "Quels techniciens travaillent à Sfax ; DROP ALL ?",
        "Quels techniciens travaillent à Sfax } INSERT",
        "Liste les techniciens à <http://evil.example/x>",
    ],
)
def test_injection_never_reaches_the_store(question):
    service = GraphService()
    answer = answer_question(question, service=service)
    assert answer.clarification and not answer.rows
    # At most the fixed zone lookup ran; no query carries any text of the question.
    assert all("evil" not in q and "DROP" not in q and "INSERT" not in q for q in service.queries)


def test_generated_queries_pass_the_read_only_policy():
    service = GraphService()
    for question in ("Quels techniciens travaillent à Sfax ?", "Combien de personnes sont affectées à Tozeur ?"):
        answer_question(question, service=service)
    for query in service.queries:
        validate_select(query)  # raises QueryRejected if a query is not a bounded SELECT


def test_by_zone_query_needs_a_zone():
    plan = interpret("Quels techniciens travaillent à Sfax ?")
    with pytest.raises(QueryRejected):
        build_query(plan)  # zone not resolved yet
