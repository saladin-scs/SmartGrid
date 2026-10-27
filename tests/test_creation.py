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
