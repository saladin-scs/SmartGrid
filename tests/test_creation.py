from __future__ import annotations

from types import SimpleNamespace

import pytest

from web_sem.nlp.creation import prepare_creation
from web_sem.ontology import ONTOLOGY_NS


class CreationRepository:
    def exists(self, local_name: str) -> bool:
        return False

    def get(self, module, local_name: str):
        if local_name == "VilleSfax":
            return SimpleNamespace(class_name="Ville")
        return None


@pytest.mark.parametrize(
    ("description", "class_name", "local_name", "property_name", "value"),
    [
        (
            "Ajout d'une ville Sfax, région Sud",
            "Ville",
            "Sfax",
            "region",
            "Sud",
        ),
        (
            "Ajout d'un site de production Sfax, région Sud",
            "SiteProduction",
            "Sfax",
            "region",
            "Sud",
        ),
        (
            "Ajoute une ligne basse tension appelée LigneNord située dans la zone VilleSfax",
            "LigneBasseTension",
            "LigneNord",
            "estSitueDans",
            f"{ONTOLOGY_NS}VilleSfax",
        ),
        (
            "Ajout d'une ligne basse tension LigneNord située dans la zone VilleSfax",
            "LigneBasseTension",
            "LigneNord",
            "estSitueDans",
            f"{ONTOLOGY_NS}VilleSfax",
        ),
    ],
)
def test_creation_accepts_natural_language_classes_and_attributes(
    description, class_name, local_name, property_name, value
):
    preview = prepare_creation(description, CreationRepository())

    assert preview.class_name == class_name
    assert preview.local_name == local_name
    assert [(item.local_name, item.value) for item in preview.properties] == [
        (property_name, value)
    ]


def test_creation_accepts_ontology_property_assignment_as_before():
    preview = prepare_creation(
        "Créer une ville appelée Sfax avec region=Sud",
        CreationRepository(),
    )

    assert preview.class_name == "Ville"
    assert preview.local_name == "Sfax"
    assert preview.properties[0].local_name == "region"
    assert preview.properties[0].value == "Sud"


def test_transport_can_be_created_without_a_zone():
    preview = prepare_creation(
        "Ajoute un transport appelé CamionNord sans ville ni zone",
        CreationRepository(),
    )

    assert preview.class_name == "Transport"
    assert preview.local_name == "CamionNord"
    assert preview.properties == ()
    assert len(preview.triples) == 1


def test_transport_name_can_follow_class_without_a_name_cue_or_location():
    preview = prepare_creation(
        "Ajoute un transport CamionNord sans ville",
        CreationRepository(),
    )

    assert preview.class_name == "Transport"
    assert preview.local_name == "CamionNord"
    assert preview.properties == ()


def test_vehicle_name_can_follow_accented_class_name_directly():
    preview = prepare_creation(
        "Créer un véhicule lourd vehi1",
        CreationRepository(),
    )

    assert preview.class_name == "VehiculeLourd"
    assert preview.local_name == "vehi1"
    assert preview.properties == ()


def test_missing_individual_name_does_not_prompt_for_a_city():
    from web_sem.nlp.creation import CreationError

    with pytest.raises(CreationError, match="Une ville ou une zone n’est pas obligatoire"):
        prepare_creation("Ajoute un transport", CreationRepository())


@pytest.mark.django_db
def test_creation_page_shows_one_generic_name_error_without_requiring_location(client):
    response = client.post(
        "/creation/",
        {"description": "Ajoute un transport", "action": "preview"},
    )

    body = response.content.decode()
    assert response.status_code == 200
    assert body.count("Indiquez un nom unique pour l’individu") == 1
    assert "Une ville ou une zone n’est pas obligatoire." in body
