"""Natural-language lookup of ontology relationships."""

import pytest

from consommateur.forms import ConsommateurForm
from infrastructure.forms import InfrastructureForm
from personne.forms import PersonneForm
from web_sem.nlp.interpret import GET_RELATIONS, interpret
from web_sem.nlp.service import SAMPLE_QUESTIONS, answer_question
from web_sem.nlp.sparql import build_query, validate_select
from web_sem.ontology import class_iri, get_property, individual_iri
from web_sem.repository import IndividualRepository


@pytest.mark.parametrize(
    ("question", "relation", "entity_name", "class_name", "property_name"),
    [
        (
            "Quels contrats sont liés au consommateur sana ?",
            "consumer_contracts",
            "sana",
            "ContratAbonnement",
            "souscritContrat",
        ),
        (
            "Quelles infrastructures sont situées dans la zone Ville_Sfax ?",
            "zone_infrastructure",
            "Ville_Sfax",
            "Infrastructure",
            "estSitueDans",
        ),
    ],
)
def test_relation_questions_generate_bounded_selects(
    question, relation, entity_name, class_name, property_name
):
    plan = interpret(question)
    query = build_query(plan)
    prop = get_property(property_name)

    assert plan.intent == GET_RELATIONS
    assert plan.relation == relation
    assert plan.entity_name == entity_name
    assert prop is not None
    assert f"<{prop.iri}>" in query
    assert f"<{individual_iri(entity_name)}>" in query
    assert f"<{class_iri(class_name)}>" in query
    assert "LIMIT 100" in query
    validate_select(query)


@pytest.mark.parametrize(
    "question",
    [
        "Quels contrats sont liés au consommateur ?",
        "Quelles infrastructures sont situées dans la zone ?",
    ],
)
def test_relation_questions_require_an_exact_entity_name(question):
    plan = interpret(question)

    assert plan.intent == ""
    assert plan.clarification


def test_related_results_are_presented_as_individuals():
    class FakeService:
        def select(self, query):
            return {
                "results": {
                    "bindings": [
                        {
                            "individual": {
                                "type": "uri",
                                "value": individual_iri("ContratAbonnement_1"),
                            },
                            "type": {
                                "type": "uri",
                                "value": class_iri("ContratAbonnement"),
                            },
                        }
                    ]
                }
            }

    answer = answer_question(
        "Quels contrats sont liés au consommateur sana ?",
        service=FakeService(),
    )

    assert [row.title for row in answer.rows] == ["ContratAbonnement_1"]
    assert answer.empty_message == ""


def test_zone_relation_falls_back_to_infrastructure_name_when_rdf_link_is_missing():
    class FakeService:
        def select(self, query):
            if "estSitueDans" in query:
                return {"results": {"bindings": []}}
            return {
                "results": {
                    "bindings": [
                        {
                            "individual": {
                                "type": "uri",
                                "value": individual_iri("AVilleSfax"),
                            },
                            "type": {
                                "type": "uri",
                                "value": class_iri("LigneBasseTension"),
                            },
                        }
                    ]
                }
            }

    answer = answer_question(
        "Quelles infrastructures sont situées dans la zone VilleSfax ?",
        service=FakeService(),
    )

    assert [row.title for row in answer.rows] == ["AVilleSfax"]
    assert "Aucun lien RDF de localisation n’a été trouvé" in answer.explanation
    assert answer.empty_message == ""


def test_relation_examples_are_supported():
    assert "Quels contrats sont liés au client abonné ClientAbonne_LacTunis ?" in SAMPLE_QUESTIONS
    assert "Quelles infrastructures sont situées dans la zone Ville_Sfax ?" in SAMPLE_QUESTIONS


def test_zone_query_covers_existing_site_types_and_relationships():
    plan = interpret("Quelles infrastructures sont situées dans la zone Ville_Sfax ?")
    query = build_query(plan)

    for property_name in ("estSitueDans", "appartientAVille"):
        prop = get_property(property_name)
        assert prop is not None
        assert f"<{prop.iri}>" in query
    assert f"<{class_iri('SiteStockage')}>" in query
    assert f"<{class_iri('Infrastructure')}>" in query
    validate_select(query)


def test_contract_query_covers_existing_and_consumer_contract_relationships():
    plan = interpret("Quels contrats sont liés au client abonné ClientAbonne_LacTunis ?")
    query = build_query(plan)

    for property_name in ("souscrit", "souscritContrat"):
        prop = get_property(property_name)
        assert prop is not None
        assert f"<{prop.iri}>" in query
    assert f"<{individual_iri('ClientAbonne_LacTunis')}>" in query
    assert f"<{class_iri('ContratAbonnement')}>" in query
    validate_select(query)


def test_consumer_form_can_link_only_contracts_in_the_object_property_range(monkeypatch):
    observed = {}

    def list_individuals(self, module, *, query="", class_name=""):
        observed["root"] = module.root
        observed["class_name"] = class_name
        return []

    monkeypatch.setattr(IndividualRepository, "list_individuals", list_individuals)
    form = ConsommateurForm()
    prop = get_property("souscritContrat")

    assert prop is not None
    assert prop.domains == (f"{prop.iri.rsplit('#', 1)[0]}#Consommateur",)
    assert prop.ranges == (f"{prop.iri.rsplit('#', 1)[0]}#ContratAbonnement",)
    assert observed == {"root": "Contrat", "class_name": "ContratAbonnement"}
    assert "prop_souscritContrat" in form.fields


def test_infrastructure_form_can_link_to_a_zone(monkeypatch):
    observed = {}

    def list_individuals(self, module, *, query="", class_name=""):
        observed["root"] = module.root
        observed["class_name"] = class_name
        return []

    monkeypatch.setattr(IndividualRepository, "list_individuals", list_individuals)
    form = InfrastructureForm()

    assert observed == {"root": "Zone", "class_name": ""}
    assert "prop_estSitueDans" in form.fields


def test_subscriber_form_can_link_only_subscription_contracts(monkeypatch):
    observed = []

    def list_individuals(self, module, *, query="", class_name=""):
        observed.append((module.root, class_name))
        return []

    monkeypatch.setattr(IndividualRepository, "list_individuals", list_individuals)
    form = PersonneForm()

    assert ("Contrat", "ContratAbonnement") in observed
    assert "prop_souscrit" in form.fields
