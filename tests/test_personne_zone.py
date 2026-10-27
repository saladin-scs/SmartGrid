from __future__ import annotations

import pytest
from django.urls import reverse

from web_sem import forms as web_forms
from web_sem import views as web_views
from web_sem.mock_repository import MockIndividualRepository
from web_sem.ontology import get_module, get_property

PERSONNE_CLASSES = {
    "Personne", "ClientAbonne", "Ingenieur", "Operateur", "Technicien",
    "TechnicienExploitation", "TechnicienMaintenance", "TechnicienLigne", "TechnicienPoste",
}
ZONE_CLASSES = {
    "Zone", "Ville", "SiteInstallation", "SiteProduction", "SiteEolien", "SiteSolaire", "SiteStockage",
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


def test_personne_hierarchy_matches_ontology():
    module = get_module("Personne")
    assert set(module.classes_by_name) == PERSONNE_CLASSES
    assert module.hierarchy("TechnicienLigne") == (
        "Personne", "Technicien", "Technicien Maintenance", "Technicien Ligne",
    )


def test_zone_hierarchy_matches_ontology():
    module = get_module("Zone")
    assert set(module.classes_by_name) == ZONE_CLASSES
    assert module.hierarchy("SiteSolaire")[-3:] == ("Site Installation", "Site Production", "Site Solaire")


@pytest.mark.parametrize(
    ("name", "domain", "range_or_object"),
    [
        ("nomPersonne", "Personne", False),
        ("matricule", "Personne", False),
        ("emailPersonne", "Personne", False),
        ("nomZone", "Zone", False),
        ("region", "Zone", False),
        ("puissanceInstalleeMW", "SiteProduction", False),
        ("estAffecteA", "Personne", True),
        ("appartientAVille", "SiteInstallation", True),
        ("residentDans", "ClientAbonne", True),
    ],
)
def test_module_properties_are_declared(name, domain, range_or_object):
    prop = get_property(name)
    assert prop is not None
    assert [iri.rsplit("#", 1)[1] for iri in prop.domains] == [domain]
    assert prop.is_object is range_or_object


@pytest.mark.parametrize(
    ("route", "class_name", "other_class"),
    [("personne", "Operateur", "Zone"), ("zone", "SiteEolien", "Operateur")],
)
def test_crud_cycle(client, repo, route, class_name, other_class):
    name_field = "prop_nomPersonne" if route == "personne" else "prop_nomZone"
    create_url = reverse(f"{route}:create")
    assert client.get(create_url).status_code == 200

    response = client.post(create_url, {"local_name": "demo_item", "rdf_type": class_name, name_field: "Demo"})
    assert response.status_code == 302
    assert repo.get(get_module("Personne" if route == "personne" else "Zone"), "demo_item")

    detail = reverse(f"{route}:detail", args=["demo_item"])
    assert client.get(detail).status_code == 200
    assert "demo_item" in client.get(reverse(f"{route}:list")).content.decode()

    # A duplicate name is rejected.
    again = client.post(create_url, {"local_name": "demo_item", "rdf_type": class_name, name_field: "Demo"})
    assert again.status_code == 200 and again.context["form"].errors["local_name"]

    # A class from another module is rejected.
    wrong = client.post(create_url, {"local_name": "other_item", "rdf_type": other_class, name_field: "X"})
    assert wrong.status_code == 200 and "rdf_type" in wrong.context["form"].errors

    assert client.post(reverse(f"{route}:delete", args=["demo_item"])).status_code == 302
    assert client.get(detail).status_code == 404


def test_search_filters_by_class(client, repo):
    module = get_module("Personne")
    repo.create(module, "amal", "Ingenieur")
    repo.create(module, "walid", "TechnicienLigne")

    only_tech = client.get(reverse("personne:list"), {"rdf_type": "Technicien"})
    names = [item.local_name for item in only_tech.context["individuals"]]
    assert names == ["walid"]  # subclasses included, siblings excluded


def test_reserved_name_is_rejected(client, repo):
    response = client.post(reverse("zone:create"), {"local_name": "Ville", "rdf_type": "Ville", "prop_nomZone": "V"})
    assert response.status_code == 200
    assert "local_name" in response.context["form"].errors


def test_person_properties_are_saved_and_shown(client, repo):
    zone = get_module("Zone")
    repo.create(zone, "ville_sfax", "Ville")
    response = client.post(
        reverse("personne:create"),
        {
            "local_name": "sami",
            "rdf_type": "TechnicienLigne",
            "prop_nomPersonne": "Sami",
            "prop_matricule": "TLG-9",
            "prop_emailPersonne": "sami@example.com",
            "prop_estAffecteA": "ville_sfax",
        },
    )
    assert response.status_code == 302
    detail = client.get(reverse("personne:detail", args=["sami"])).content.decode()
    assert "TLG-9" in detail and "ville_sfax" in detail
    # The zone page lists the incoming link.
    assert "sami" in client.get(reverse("zone:detail", args=["ville_sfax"])).content.decode()


def test_edit_updates_and_clears_properties(client, repo):
    person = get_module("Personne")
    repo.create(person, "amal", "Ingenieur", {"nomPersonne": "Amal", "matricule": "OLD"})
    response = client.post(
        reverse("personne:edit", args=["amal"]),
        {"rdf_type": "Ingenieur", "prop_nomPersonne": "Amal B", "prop_matricule": ""},
    )
    assert response.status_code == 302
    assert repo.get(person, "amal").property_map() == {"nomPersonne": "Amal B"}


def test_class_specific_properties_are_rejected_elsewhere(client, repo):
    zone = client.post(
        reverse("zone:create"),
        {"local_name": "gafsa", "rdf_type": "Ville", "prop_nomZone": "Gafsa", "prop_puissanceInstalleeMW": "10"},
    )
    assert zone.status_code == 200 and "prop_puissanceInstalleeMW" in zone.context["form"].errors
    person = client.post(
        reverse("personne:create"),
        {"local_name": "rim", "rdf_type": "Operateur", "prop_nomPersonne": "Rim", "prop_residentDans": "x"},
    )
    assert person.status_code == 200 and "prop_residentDans" in person.context["form"].errors


def test_scenarios_build_valid_sparql():
    from rdflib.plugins.sparql import prepareQuery

    from web_sem import scenarios

    for item in scenarios.SCENARIOS:
        query = scenarios.build_query(item.key, "ville_sfax")
        prepareQuery(query)  # raises on a syntax error


def test_scenarios_run_against_a_graph(client, monkeypatch):
    from rdflib import Graph

    from web_sem import scenarios

    graph = Graph().parse("data/ontology/ENERGIE.rdf")

    class GraphService:
        def select(self, query):
            result = graph.query(query)
            return {
                "results": {
                    "bindings": [
                        {str(v): {"value": str(row[v])} for v in result.vars if row[v] is not None}
                        for row in result
                    ]
                }
            }

    rows = scenarios.run(scenarios.BY_KEY["effectif_par_zone"], service=GraphService())[1]
    assert ["Ville_Sfax", "2"] in rows
    techs = scenarios.run(scenarios.BY_KEY["techniciens_zone"], "Ville_Tozeur", GraphService())[1]
    assert any(row[1] == "TechnicienPoste_Rim" for row in techs)
    power = scenarios.run(scenarios.BY_KEY["puissance_par_type"], service=GraphService())[1]
    assert {row[0] for row in power} == {"SiteSolaire", "SiteEolien"}
    unassigned = scenarios.run(scenarios.BY_KEY["sans_affectation"], service=GraphService())[1]
    assert unassigned == [["Technicien_Walid", "Technicien"]]


def test_scenario_pages_report_unavailable_store(client, monkeypatch):
    from web_sem import scenarios
    from web_sem.sparql import SparqlServiceError

    def boom(*args, **kwargs):
        raise SparqlServiceError("down")

    monkeypatch.setattr(scenarios, "run", boom)
    assert client.get(reverse("scenarios")).status_code == 200
    assert client.get(reverse("scenario_run", args=["effectif_par_zone"])).status_code == 503
    assert client.get(reverse("scenario_run", args=["nope"])).status_code == 404


def test_list_shows_name_zone_hierarchy_and_class_counts(client, repo):
    zone = get_module("Zone")
    person = get_module("Personne")
    repo.create(zone, "ville_sfax", "Ville", {"nomZone": "Sfax"})
    repo.create(person, "sami", "TechnicienLigne", {"nomPersonne": "Sami Ben Ali", "estAffecteA": "ville_sfax"})
    repo.create(person, "amal", "Ingenieur", {"nomPersonne": "Amal"})

    page = client.get(reverse("personne:list"))
    html = page.content.decode()
    assert "Sami Ben Ali" in html and "ville_sfax" in html
    assert "Personne / Technicien / Technicien Maintenance / Technicien Ligne" in html
    assert [(c["label"], c["count"]) for c in page.context["class_counts"]] == [
        ("Ingenieur", 1),
        ("Technicien Ligne", 1),
    ]
    zones = client.get(reverse("zone:list")).content.decode()
    assert "Sfax" in zones
