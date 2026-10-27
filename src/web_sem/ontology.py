"""Read class hierarchies from ENERGIE.rdf.

The file is the ontology. Individuals are not copied out of it; Fuseki stores those.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

from django.conf import settings
from rdflib import Graph, URIRef
from rdflib.namespace import OWL, RDF, RDFS

ONTOLOGY_NS = "http://www.semanticweb.org/sanal/ontologies/2026/9/untitled-ontology-9#"
LOCAL_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
MAX_LOCAL_NAME = 80
_DISPLAY_BOUNDARY = re.compile(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")

_MODULE_KEYS = {
    "Personne": "personne",
    "SourceProduction": "source_production",
    "Stockage": "stockage",
    "Consommateur": "consommateur",
    "Contrat": "contrat",
    "Infrastructure": "infrastructure",
    "Transport": "transport",
    "Zone": "zone",
    "Evenement": "evenement",
    "CapteurDispositif": "capteur_dispositif",
}


class OntologyError(Exception):
    """ENERGIE.rdf could not be read."""


@dataclass(frozen=True, slots=True)
class OntologyClass:
    local_name: str
    iri: str
    parent: str | None
    depth: int
    display_name: str


@dataclass(frozen=True, slots=True)
class OntologyProperty:
    local_name: str
    iri: str
    domains: tuple[str, ...]
    ranges: tuple[str, ...]
    is_object: bool


@dataclass(frozen=True, slots=True)
class OntologyModule:
    root: str
    key: str
    classes: tuple[OntologyClass, ...]
    classes_by_name: dict[str, OntologyClass]

    @property
    def list_url_name(self) -> str:
        return f"{self.key}:list"

    @property
    def detail_url_name(self) -> str:
        return f"{self.key}:detail"

    @property
    def create_url_name(self) -> str:
        return f"{self.key}:create"

    @property
    def edit_url_name(self) -> str:
        return f"{self.key}:edit"

    @property
    def delete_url_name(self) -> str:
        return f"{self.key}:delete"

    def choice_tuples(self) -> list[tuple[str, str]]:
        return [
            (item.local_name, f"{'– ' * item.depth}{item.display_name}")
            for item in self.classes
        ]

    def subtree_iris(self, local_name: str | None) -> list[str]:
        if not local_name:
            return [item.iri for item in self.classes]
        selected = self.classes_by_name.get(local_name)
        if selected is None:
            return []
        names = {local_name}
        changed = True
        while changed:
            changed = False
            for item in self.classes:
                if item.parent in names and item.local_name not in names:
                    names.add(item.local_name)
                    changed = True
        return [item.iri for item in self.classes if item.local_name in names]

    def hierarchy(self, local_name: str) -> tuple[str, ...]:
        names: list[str] = []
        seen: set[str] = set()
        current: str | None = local_name
        while current and current not in seen:
            seen.add(current)
            item = self.classes_by_name.get(current)
            if item is None:
                break
            names.append(item.display_name)
            current = item.parent
        names.reverse()
        return tuple(names)


@dataclass(frozen=True, slots=True)
class Catalog:
    modules: dict[str, OntologyModule]
    reserved_names: frozenset[str]
    properties: dict[str, OntologyProperty]


def display_name(local_name: str) -> str:
    return _DISPLAY_BOUNDARY.sub(" ", local_name)


def individual_iri(local_name: str) -> str:
    if not LOCAL_NAME_RE.fullmatch(local_name) or len(local_name) > MAX_LOCAL_NAME:
        raise ValueError(f"Unsafe individual name: {local_name!r}")
    return f"{ONTOLOGY_NS}{local_name}"


def class_iri(local_name: str) -> str:
    if not LOCAL_NAME_RE.fullmatch(local_name):
        raise ValueError(f"Unsafe class name: {local_name!r}")
    return f"{ONTOLOGY_NS}{local_name}"


def get_module(root_name: str) -> OntologyModule:
    try:
        return load_catalog().modules[root_name]
    except KeyError as exc:
        raise OntologyError(f"Unknown ontology module: {root_name}") from exc


def list_modules() -> tuple[OntologyModule, ...]:
    catalog = load_catalog()
    return tuple(catalog.modules[name] for name in _MODULE_KEYS)


def reserved_names() -> frozenset[str]:
    return load_catalog().reserved_names


def list_properties() -> tuple[OntologyProperty, ...]:
    return tuple(load_catalog().properties.values())


def get_property(local_name: str) -> OntologyProperty | None:
    return load_catalog().properties.get(local_name)


@lru_cache(maxsize=1)
def load_catalog() -> Catalog:
    path = settings.BASE_DIR / "data" / "ontology" / "ENERGIE.rdf"
    graph = Graph()
    try:
        graph.parse(path)
    except Exception as exc:
        raise OntologyError(f"Could not read {path.name}: {exc}") from exc

    parents: dict[str, str] = {}
    children: dict[str, list[str]] = {}
    class_names: set[str] = set()

    for subject in graph.subjects(RDF.type, OWL.Class):
        name = _local_name(subject)
        if name:
            class_names.add(name)

    for child, parent in graph.subject_objects(RDFS.subClassOf):
        child_name = _local_name(child)
        parent_name = _local_name(parent)
        if not child_name or not parent_name or child_name in parents:
            continue
        class_names.add(child_name)
        class_names.add(parent_name)
        parents[child_name] = parent_name
        children.setdefault(parent_name, []).append(child_name)

    for kids in children.values():
        kids.sort()

    modules = {
        root: _module(root, key, children)
        for root, key in _MODULE_KEYS.items()
        if root in class_names
    }
    missing = [root for root in _MODULE_KEYS if root not in modules]
    if missing:
        raise OntologyError(f"ENERGIE.rdf has no class for: {', '.join(missing)}")

    reserved = set(class_names)
    properties: dict[str, OntologyProperty] = {}
    for property_type in (OWL.ObjectProperty, OWL.DatatypeProperty):
        for subject in graph.subjects(RDF.type, property_type):
            name = _local_name(subject)
            if name:
                reserved.add(name)
                properties[name] = OntologyProperty(
                    local_name=name,
                    iri=str(subject),
                    domains=tuple(str(term) for term in graph.objects(subject, RDFS.domain)),
                    ranges=tuple(str(term) for term in graph.objects(subject, RDFS.range)),
                    is_object=property_type == OWL.ObjectProperty,
                )

    return Catalog(
        modules=modules,
        reserved_names=frozenset(reserved),
        properties=properties,
    )


def _module(root: str, key: str, children: dict[str, list[str]]) -> OntologyModule:
    ordered: list[OntologyClass] = []
    seen: set[str] = set()

    def walk(name: str, parent: str | None, depth: int) -> None:
        if name in seen:
            return
        seen.add(name)
        ordered.append(
            OntologyClass(
                local_name=name,
                iri=class_iri(name),
                parent=parent,
                depth=depth,
                display_name=display_name(name),
            )
        )
        for child in children.get(name, []):
            walk(child, name, depth + 1)

    walk(root, None, 0)
    return OntologyModule(
        root=root,
        key=key,
        classes=tuple(ordered),
        classes_by_name={item.local_name: item for item in ordered},
    )


def _local_name(term: object) -> str | None:
    if not isinstance(term, URIRef):
        return None
    text = str(term)
    if not text.startswith(ONTOLOGY_NS):
        return None
    name = text[len(ONTOLOGY_NS) :]
    if not LOCAL_NAME_RE.fullmatch(name):
        return None
    return name
