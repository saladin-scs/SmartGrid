"""SPARQL persistence for ontology individuals.

Only INSERT and DELETE updates are sent, and only for IRIs taken from
ENERGIE.rdf or from a validated individual name.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal
from django.conf import settings

from web_sem.ontology import (
    ONTOLOGY_NS,
    OntologyModule,
    get_property,
    individual_iri,
)
from web_sem.sparql import SparqlService


@dataclass(frozen=True, slots=True)
class PropertyValue:
    name: str
    value: str
    is_object: bool = False


@dataclass(frozen=True, slots=True)
class Individual:
    local_name: str
    iri: str
    class_name: str
    class_display: str
    hierarchy: tuple[str, ...]
    properties: tuple[PropertyValue, ...] = ()
    incoming: tuple[PropertyValue, ...] = ()

    def property_map(self) -> dict[str, str]:
        return {item.name: item.value for item in self.properties}


class IndividualRepository:
    def __new__(cls, *args, **kwargs):
        if getattr(settings, "USE_MOCK_RDF", False):
            from .mock_repository import MockIndividualRepository
            return MockIndividualRepository()
        return super().__new__(cls)

    def __init__(self, service: SparqlService | None = None) -> None:
        if not hasattr(self, "service"):  # Don't re-init if it's the mock
            self.service = service or SparqlService()

    def list_individuals(
        self,
        module: OntologyModule,
        *,
        query: str = "",
        class_name: str = "",
    ) -> list[Individual]:
        iris = module.subtree_iris(class_name or None)
        if class_name and not iris:
            return []
        name_filter = ""
        if query:
            name_filter = f"FILTER(CONTAINS(LCASE(?name), LCASE({_literal(query)})))"
        payload = self.service.select(
            f"""
            SELECT ?individual ?type
            WHERE {{
              VALUES ?type {{ {_iris(iris)} }}
              ?individual a ?type .
              BIND(STRAFTER(STR(?individual), "#") AS ?name)
              {name_filter}
            }}
            ORDER BY LCASE(?name)
            """
        )
        grouped: dict[str, list[str]] = {}
        for binding in payload["results"]["bindings"]:
            iri = _term(binding, "individual")
            type_name = _fragment(_term(binding, "type"))
            if not iri.startswith(ONTOLOGY_NS) or not type_name:
                continue
            grouped.setdefault(iri, []).append(type_name)
        individuals = [
            individual
            for iri, types in grouped.items()
            if (individual := self._individual(module, iri, types)) is not None
        ]
        return individuals

    def get(self, module: OntologyModule, local_name: str) -> Individual | None:
        iri = individual_iri(local_name)
        payload = self.service.select(
            f"""
            SELECT ?type
            WHERE {{
              VALUES ?type {{ {_iris(module.subtree_iris(None))} }}
              <{iri}> a ?type .
            }}
            """
        )
        types = [
            name
            for binding in payload["results"]["bindings"]
            if (name := _fragment(_term(binding, "type")))
        ]
        if not types:
            return None
        individual = self._individual(module, iri, types)
        if individual is None:
            return None
        return replace(
            individual,
            properties=self.properties_of(local_name),
            incoming=self.incoming_of(local_name),
        )

    def properties_of(self, local_name: str) -> tuple[PropertyValue, ...]:
        iri = individual_iri(local_name)
        payload = self.service.select(
            f"""
            SELECT ?p ?o
            WHERE {{
              <{iri}> ?p ?o .
              FILTER(STRSTARTS(STR(?p), "{ONTOLOGY_NS}"))
            }}
            ORDER BY ?p
            """
        )
        return tuple(_property_values(payload, "p", "o"))

    def incoming_of(self, local_name: str) -> tuple[PropertyValue, ...]:
        iri = individual_iri(local_name)
        payload = self.service.select(
            f"""
            SELECT ?p ?s
            WHERE {{
              ?s ?p <{iri}> .
              FILTER(STRSTARTS(STR(?p), "{ONTOLOGY_NS}"))
            }}
            ORDER BY ?p ?s
            """
        )
        return tuple(_property_values(payload, "p", "s", force_object=True))

    def set_properties(self, local_name: str, values: dict[str, str]) -> None:
        """Replace the given ontology properties; empty values only delete."""
        updates = _property_updates(local_name, values)
        if updates:
            self.service.update(updates)

    def exists(self, local_name: str) -> bool:
        iri = individual_iri(local_name)
        payload = self.service.select(
            f"""
            SELECT ?p
            WHERE {{
              {{ <{iri}> ?p ?o }}
              UNION
              {{ ?s ?p <{iri}> }}
            }}
            LIMIT 1
            """
        )
        return bool(payload["results"]["bindings"])

    def create(
        self,
        module: OntologyModule,
        local_name: str,
        class_name: str,
        properties: dict[str, str] | None = None,
    ) -> None:
        iri = individual_iri(local_name)
        self.service.update(
            f"INSERT DATA {{ <{iri}> a <{module.classes_by_name[class_name].iri}> . }}"
        )
        if properties:
            self.set_properties(local_name, properties)

    def update_class(self, module: OntologyModule, local_name: str, class_name: str) -> None:
        iri = individual_iri(local_name)
        class_iri = module.classes_by_name[class_name].iri
        self.service.update(
            f"""
            DELETE {{
              <{iri}> a ?type .
            }}
            WHERE {{
              VALUES ?type {{ {_iris(module.subtree_iris(None))} }}
              <{iri}> a ?type .
            }} ;
            INSERT DATA {{
              <{iri}> a <{class_iri}> .
            }}
            """
        )

    def delete(self, local_name: str) -> None:
        iri = individual_iri(local_name)
        self.service.update(
            f"DELETE WHERE {{ <{iri}> ?p ?o }} ; DELETE WHERE {{ ?s ?p <{iri}> }}"
        )

    def _individual(
        self,
        module: OntologyModule,
        iri: str,
        type_names: list[str],
    ) -> Individual | None:
        known = [name for name in type_names if name in module.classes_by_name]
        if not known:
            return None
        class_name = max(known, key=lambda name: module.classes_by_name[name].depth)
        local_name = iri[len(ONTOLOGY_NS) :]
        ontology_class = module.classes_by_name[class_name]
        return Individual(
            local_name=local_name,
            iri=iri,
            class_name=class_name,
            class_display=ontology_class.display_name,
            hierarchy=module.hierarchy(class_name),
        )


def _iris(iris: list[str]) -> str:
    return " ".join(f"<{iri}>" for iri in iris)


def _literal(value: str) -> str:
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "")
    )
    return f'"{escaped}"'


def _term(binding: dict, name: str) -> str:
    term = binding.get(name) or {}
    value = term.get("value", "")
    return value if isinstance(value, str) else ""


def _fragment(iri: str) -> str | None:
    if "#" not in iri:
        return None
    return iri.rsplit("#", 1)[-1]


def _property_values(
    payload: dict, predicate: str, value: str, *, force_object: bool = False
) -> list[PropertyValue]:
    items = []
    for binding in payload["results"]["bindings"]:
        name = _fragment(_term(binding, predicate))
        term = binding.get(value) or {}
        text = _term(binding, value)
        if not name or not text:
            continue
        is_object = force_object or term.get("type") == "uri"
        if is_object:
            if not text.startswith(ONTOLOGY_NS):
                continue
            text = text[len(ONTOLOGY_NS) :]
        items.append(PropertyValue(name=name, value=text, is_object=is_object))
    return items


def _property_updates(local_name: str, values: dict[str, str]) -> str:
    """DELETE then INSERT for each known ontology property in `values`."""
    iri = individual_iri(local_name)
    statements = []
    for name, raw in values.items():
        prop = get_property(name)
        if prop is None:
            raise ValueError(f"Unknown ontology property: {name}")
        statements.append(f"DELETE WHERE {{ <{iri}> <{prop.iri}> ?o }}")
        raw = (raw or "").strip()
        if not raw:
            continue
        if prop.is_object:
            obj = f"<{individual_iri(raw)}>"
        elif prop.ranges and prop.ranges[0].endswith("#decimal"):
            obj = f'"{Decimal(raw)}"^^<http://www.w3.org/2001/XMLSchema#decimal>'
        else:
            obj = f"{_literal(raw)}^^<http://www.w3.org/2001/XMLSchema#string>"
        statements.append(f"INSERT DATA {{ <{iri}> <{prop.iri}> {obj} . }}")
    return " ;\n".join(statements)
