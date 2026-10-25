"""SPARQL persistence for ontology individuals.

Only INSERT and DELETE updates are sent, and only for IRIs taken from
ENERGIE.rdf or from a validated individual name.
"""

from __future__ import annotations

from dataclasses import dataclass

from web_sem.ontology import (
    ONTOLOGY_NS,
    OntologyModule,
    individual_iri,
)
from web_sem.sparql import SparqlService


@dataclass(frozen=True, slots=True)
class Individual:
    local_name: str
    iri: str
    class_name: str
    class_display: str
    hierarchy: tuple[str, ...]


class IndividualRepository:
    def __init__(self, service: SparqlService | None = None) -> None:
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
        return self._individual(module, iri, types)

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

    def create(self, module: OntologyModule, local_name: str, class_name: str) -> None:
        iri = individual_iri(local_name)
        self.service.update(
            f"INSERT DATA {{ <{iri}> a <{module.classes_by_name[class_name].iri}> . }}"
        )

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
