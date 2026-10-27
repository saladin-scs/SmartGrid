from __future__ import annotations

import pytest
from django.urls import reverse

from web_sem.intelligence import dashboard_summary, knowledge_graph
from web_sem.ontology import class_iri, get_property, individual_iri


class FakeSparql:
    def __init__(self, responses: list[dict]) -> None:
        self.responses = responses
        self.queries: list[str] = []

    def select(self, query: str) -> dict:
        self.queries.append(query)
        return self.responses[len(self.queries) - 1]


def _bindings(*bindings: dict) -> dict:
    return {"results": {"bindings": list(bindings)}}


@pytest.mark.django_db
def test_dashboard_uses_fuseki_counts_and_returns_typed_distribution():
    service = FakeSparql(
        [
            _bindings(
                {"type": {"value": class_iri("Personne")}, "count": {"value": "2"}},
                {"type": {"value": class_iri("Consommateur")}, "count": {"value": "1"}},
            ),
            _bindings({"total": {"value": "3"}}),
        ]
    )

    summary = dashboard_summary(service)

    assert summary["total_individuals"] == 3
    assert summary["typed_classes"] == 2
    assert summary["type_distribution"] == [
        {"name": "Personne", "label": "Personne", "count": 2},
        {"name": "Consommateur", "label": "Consommateur", "count": 1},
    ]
    assert len(service.queries) == 2
    assert all("SELECT" in query for query in service.queries)
    assert all("LIMIT" not in query for query in service.queries)


@pytest.mark.django_db
def test_graph_serializes_actual_individual_class_and_literal_relationship():
    predicate = get_property("nomPersonne")
    assert predicate is not None
    service = FakeSparql(
        [
            _bindings(
                {
                    "subject": {"type": "uri", "value": individual_iri("Amal")},
                    "type": {"type": "uri", "value": class_iri("Personne")},
                    "predicate": {"type": "uri", "value": predicate.iri},
                    "object": {
                        "type": "literal",
                        "value": "Amal",
                        "datatype": "http://www.w3.org/2001/XMLSchema#string",
                    },
                }
            )
        ]
    )

    payload = knowledge_graph("Personne", service)

    nodes = {node["data"]["id"]: node["data"] for node in payload["nodes"]}
    assert nodes[individual_iri("Amal")]["kind"] == "individual"
    assert nodes[class_iri("Personne")]["kind"] == "class"
    assert any(node["kind"] == "literal" and node["label"] == "Amal" for node in nodes.values())
    assert len(payload["edges"]) == 2
    assert "LIMIT 180" in service.queries[0]
    assert class_iri("Personne") in service.queries[0]


@pytest.mark.django_db
def test_graph_rejects_unknown_class_before_querying_fuseki():
    service = FakeSparql([])

    with pytest.raises(ValueError, match="Unknown ontology class"):
        knowledge_graph("UnknownEnergyClass", service)

    assert service.queries == []


@pytest.mark.django_db
def test_graph_returns_an_explicit_empty_payload_when_fuseki_has_no_results():
    service = FakeSparql([_bindings()])

    payload = knowledge_graph(service=service)

    assert payload == {"nodes": [], "edges": [], "truncated": False, "limit": 180}
    assert len(service.queries) == 1


@pytest.mark.django_db
def test_intelligence_routes_are_available(client, monkeypatch):
    monkeypatch.setattr(
        "web_sem.views.dashboard_summary",
        lambda: {
            "total_individuals": 0,
            "typed_classes": 0,
            "type_distribution": [],
            "modules": (),
            "available": True,
        },
    )
    monkeypatch.setattr(
        "web_sem.views.knowledge_graph",
        lambda class_name: {"nodes": [], "edges": [], "truncated": False, "limit": 180},
    )

    overview = client.get(reverse("overview"))
    graph = client.get(reverse("graph"))
    data = client.get(reverse("graph_data"))

    assert overview.status_code == 200
    assert b"INDIVIDUS RDF" in overview.content
    assert graph.status_code == 200
    assert b"Relations RDF" in graph.content
    assert data.status_code == 200
    assert data.json() == {"nodes": [], "edges": [], "truncated": False, "limit": 180}
