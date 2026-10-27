from __future__ import annotations

import pytest

from web_sem.nlp.interpret import (
    COUNT_INDIVIDUALS,
    FILTER_BY_CLASS,
    GET_DETAILS,
    interpret,
)
from web_sem.nlp.service import answer_question
from web_sem.ontology import individual_iri


@pytest.mark.parametrize(
    ("question", "intent", "class_name"),
    [
        ("Liste les lignes haute tensoin souterraines.", FILTER_BY_CLASS, "LigneHauteTensionSouterraine"),
        ("Combien de camions de livraisno existe-t-il ?", COUNT_INDIVIDUALS, "CamionLivraison"),
        ("List the heavyy goods vehicle.", FILTER_BY_CLASS, "VehiculeLourd"),
        ("Show overhed low voltage lines.", FILTER_BY_CLASS, "LigneBasseTensionAerienne"),
    ],
)
def test_fuzzy_matching_recognizes_infrastructure_and_transport_classes(
    question, intent, class_name
):
    plan = interpret(question)

    assert plan.intent == intent
    assert plan.class_name == class_name
    assert plan.clarification == ""


def test_fuzzy_matching_does_not_guess_between_similarly_named_transport_classes():
    plan = interpret("Liste les camoin.")

    assert plan.intent == ""
    assert plan.clarification
    assert "Camion Grue" in plan.clarification
    assert "Camion Nacelle" in plan.clarification


class IndividualLookupService:
    def __init__(self, names: list[str], class_name: str = "VehiculeLourd") -> None:
        self.names = names
        self.class_name = class_name
        self.queries: list[str] = []

    def select(self, query: str) -> dict:
        self.queries.append(query)
        if query.startswith("SELECT ?individual\n"):
            return {
                "results": {
                    "bindings": [
                        {"individual": {"value": individual_iri(name)}}
                        for name in self.names
                    ]
                }
            }
        if query.startswith("SELECT ?individual ?type"):
            matching = [
                name for name in self.names
                if f"<{individual_iri(name)}>" in query
            ]
            return {
                "results": {
                    "bindings": [
                        {
                            "individual": {"value": individual_iri(name)},
                            "type": {
                                "value": (
                                    "http://www.semanticweb.org/sanal/ontologies/2026/9/"
                                    f"untitled-ontology-9#{self.class_name}"
                                )
                            },
                        }
                        for name in matching
                    ]
                }
            }
        return {"results": {"bindings": []}}


def test_details_fuzzy_match_an_individual_name_created_in_the_dataset():
    service = IndividualLookupService(["VehiculeLourdVehi1"])

    answer = answer_question(
        "Affiche les détails de VehiculeLourdVehiI",
        service=service,
    )

    assert answer.intent == GET_DETAILS
    assert answer.clarification == ""
    assert answer.rows[0].title == "VehiculeLourdVehi1"
    assert len(service.queries) == 4
    assert any("VehiculeLourdVehi1" in query for query in service.queries)


def test_details_fuzzy_match_existing_infrastructure_individual():
    service = IndividualLookupService(["AVilleSfax"], class_name="LigneBasseTension")

    answer = answer_question(
        "Affiche les détails de AVilleSfa",
        service=service,
    )

    assert answer.intent == GET_DETAILS
    assert answer.clarification == ""
    assert answer.rows[0].title == "AVilleSfax"
    assert answer.rows[0].href == "/infrastructures/i/AVilleSfax/"
    assert answer.rows[0].meta == "Infrastructure / Ligne Transport / Ligne Basse Tension"


def test_details_fuzzy_match_asks_when_individual_names_are_ambiguous():
    service = IndividualLookupService(["VehiculeLourdVehi1", "VehiculeLourdVehi2"])

    answer = answer_question(
        "Affiche les détails de VehiculeLourdVehi",
        service=service,
    )

    assert answer.intent == GET_DETAILS
    assert answer.clarification
    assert "VehiculeLourdVehi1" in answer.clarification
    assert "VehiculeLourdVehi2" in answer.clarification
    assert len(service.queries) == 2
