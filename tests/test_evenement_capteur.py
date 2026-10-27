from __future__ import annotations

import pytest
from django.urls import reverse

from web_sem import forms as web_forms
from web_sem import views as web_views
from web_sem.mock_repository import MockIndividualRepository
from web_sem.nlp.interpret import (
    COUNT_INDIVIDUALS,
    FILTER_BY_CLASS,
    GET_DETAILS,
    GET_RELATIONS,
    LIST_INDIVIDUALS,
    LIST_TYPES,
    interpret,
)
from web_sem.nlp.service import answer_question
from web_sem.nlp.sparql import build_query, validate_select
from web_sem.ontology import class_iri, get_module, get_property, individual_iri

EVENEMENT_CLASSES = {
    "Evenement",
    "AlerteSurcharge",
    "Maintenance",
    "MaintenanceCorrective",
    "MaintenancePreventive",
    "Panne",
    "PanneElectrique",
    "CoupureAlimentation",
    "CourtCircuit",
    "PanneMecanique",
}

CAPTEUR_CLASSES = {
    "CapteurDispositif",
    "CapteurProduction",
    "CapteurProductionRenouvelable",
    "CapteurEolien",
    "CapteurPhotovoltaique",
    "CapteurProductionThermique",
    "CompteurIntelligent",
}


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """Back the CRUD views with the JSON mock repository in a temp file."""
    instance = MockIndividualRepository()
    instance.path = tmp_path / "individuals.json"
    instance.props_path = tmp_path / "properties.json"
    instance._ensure_file()
    factory = lambda: instance  # noqa: E731
    monkeypatch.setattr(web_views, "IndividualRepository", factory)
    monkeypatch.setattr(web_forms, "IndividualRepository", factory)
    return instance


def test_evenement_hierarchy_matches_ontology():
    module = get_module("Evenement")
    assert set(module.classes_by_name) == EVENEMENT_CLASSES
    assert module.hierarchy("CoupureAlimentation") == (
        "Evenement",
        "Panne",
        "Panne Electrique",
        "Coupure Alimentation",
    )
    assert module.hierarchy("MaintenanceCorrective") == (
        "Evenement",
        "Maintenance",
        "Maintenance Corrective",
    )


def test_capteur_hierarchy_matches_ontology():
    module = get_module("CapteurDispositif")
    assert set(module.classes_by_name) == CAPTEUR_CLASSES
    assert module.hierarchy("CapteurEolien") == (
        "Capteur Dispositif",
        "Capteur Production",
        "Capteur Production Renouvelable",
        "Capteur Eolien",
    )
    assert module.hierarchy("CompteurIntelligent") == (
        "Capteur Dispositif",
        "Compteur Intelligent",
    )


@pytest.mark.parametrize(
    ("name", "domain", "range_or_object"),
    [
        ("dateEvenement", "Evenement", False),
        ("concerne", "Maintenance", True),
        ("declenche", "CapteurDispositif", True),
    ],
)
def test_evenement_capteur_properties_declared(name, domain, range_or_object):
    prop = get_property(name)
    assert prop is not None
    assert [iri.rsplit("#", 1)[1] for iri in prop.domains] == [domain]
    assert prop.is_object is range_or_object


@pytest.mark.parametrize(
    ("route", "module_root", "class_name", "other_class", "property_field", "property_val"),
    [
        ("evenement", "Evenement", "CoupureAlimentation", "Zone", "prop_dateEvenement", "2026-10-27"),
        ("capteur_dispositif", "CapteurDispositif", "CapteurEolien", "Personne", "prop_declenche", ""),
    ],
)
def test_crud_cycle(client, repo, route, module_root, class_name, other_class, property_field, property_val):
    module = get_module(module_root)
    create_url = reverse(f"{route}:create")
    assert client.get(create_url).status_code == 200

    payload = {"local_name": "test_item", "rdf_type": class_name}
    if property_val:
        payload[property_field] = property_val

    # Create
    response = client.post(create_url, payload)
    assert response.status_code == 302
    assert repo.get(module, "test_item") is not None

    # Detail
    detail_url = reverse(f"{route}:detail", args=["test_item"])
    detail_resp = client.get(detail_url)
    assert detail_resp.status_code == 200
    assert "test_item" in detail_resp.content.decode()

    # List
    list_url = reverse(f"{route}:list")
    list_resp = client.get(list_url)
    assert list_resp.status_code == 200
    assert "test_item" in list_resp.content.decode()

    # Edit
    edit_url = reverse(f"{route}:edit", args=["test_item"])
    assert client.get(edit_url).status_code == 200
    edit_resp = client.post(edit_url, {"rdf_type": class_name, property_field: property_val})
    assert edit_resp.status_code == 302

    # Reject duplicate
    again = client.post(create_url, payload)
    assert again.status_code == 200
    assert "local_name" in again.context["form"].errors

    # Reject wrong class from another module
    wrong = client.post(create_url, {"local_name": "other_item", "rdf_type": other_class})
    assert wrong.status_code == 200
    assert "rdf_type" in wrong.context["form"].errors

    # Delete
    delete_url = reverse(f"{route}:delete", args=["test_item"])
    del_resp = client.post(delete_url)
    assert del_resp.status_code == 302
    assert client.get(detail_url).status_code == 404


def test_search_filters_by_class(client, repo):
    module = get_module("Evenement")
    repo.create(module, "panne_electrique_1", "PanneElectrique")
    repo.create(module, "alerte_1", "AlerteSurcharge")

    list_url = reverse("evenement:list")
    resp_filtered = client.get(list_url, {"rdf_type": "AlerteSurcharge"})
    assert resp_filtered.status_code == 200
    content = resp_filtered.content.decode()
    assert "alerte_1" in content
    assert "panne_electrique_1" not in content


@pytest.mark.parametrize(
    ("question", "intent", "class_name"),
    [
        ("Liste les événements.", LIST_INDIVIDUALS, "Evenement"),
        ("Liste les capteurs.", LIST_INDIVIDUALS, "CapteurDispositif"),
        ("Combien de pannes existe-t-il ?", COUNT_INDIVIDUALS, "Panne"),
        ("Combien de capteurs existe-t-il ?", COUNT_INDIVIDUALS, "CapteurDispositif"),
        ("Liste les pannes électriques.", FILTER_BY_CLASS, "PanneElectrique"),
        ("Liste les coupures d'alimentation.", FILTER_BY_CLASS, "CoupureAlimentation"),
        ("Liste les capteurs éoliens.", FILTER_BY_CLASS, "CapteurEolien"),
        ("Combien de compteurs intelligents existe-t-il ?", COUNT_INDIVIDUALS, "CompteurIntelligent"),
        ("Quels types de maintenance sont disponibles ?", LIST_TYPES, "Maintenance"),
        ("Quels types de capteurs de production sont disponibles ?", LIST_TYPES, "CapteurProduction"),
    ],
)
def test_nlp_intent_and_class_resolution(question, intent, class_name):
    plan = interpret(question)
    assert plan.intent == intent
    assert plan.class_name == class_name
    query = build_query(plan)
    validate_select(query)
    assert f"<{class_iri(class_name)}>" in query


def test_nlp_details_query():
    plan = interpret("Affiche les détails de Panne_1.")
    assert plan.intent == GET_DETAILS
    assert plan.individual_name == "Panne_1"
    query = build_query(plan)
    validate_select(query)
    assert f"<{individual_iri('Panne_1')}>" in query


def test_nlp_relation_sensor_events():
    plan = interpret("Quels événements sont liés au capteur CapteurEolien_1 ?")
    assert plan.intent == GET_RELATIONS
    assert plan.relation == "sensor_events"
    assert plan.entity_name == "CapteurEolien_1"
    query = build_query(plan)
    validate_select(query)
    assert "declenche" in query
