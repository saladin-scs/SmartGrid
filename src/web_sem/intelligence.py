"""Read-only dashboard and knowledge-graph queries for Fuseki."""

from __future__ import annotations

from typing import Any

from web_sem.ontology import ONTOLOGY_NS, OntologyClass, list_modules
from web_sem.sparql import SparqlService

DASHBOARD_TYPE_LIMIT = 12
GRAPH_TRIPLE_LIMIT = 180
_RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"


def dashboard_summary(service: SparqlService | None = None) -> dict[str, Any]:
    modules = list_modules()
    classes = [item for module in modules for item in module.classes]
    type_values = _iri_values(classes)
    query_service = service or SparqlService()

    distribution = query_service.select(
        f"""
        SELECT ?type (COUNT(DISTINCT ?individual) AS ?count)
        WHERE {{
          VALUES ?type {{ {type_values} }}
          OPTIONAL {{ ?individual a ?type . }}
        }}
        GROUP BY ?type
        """
    )
    total_result = query_service.select(
        f"""
        SELECT (COUNT(DISTINCT ?individual) AS ?total)
        WHERE {{
          VALUES ?type {{ {type_values} }}
          ?individual a ?type .
        }}
        """
    )

    class_by_iri = {item.iri: item for item in classes}
    counts = []
    for binding in distribution["results"]["bindings"]:
        item = class_by_iri.get(_binding_value(binding, "type"))
        if item is None:
            continue
        count = int(_binding_value(binding, "count"))
        if count:
            counts.append({"name": item.local_name, "label": item.display_name, "count": count})
    counts.sort(key=lambda item: (-item["count"], item["label"].casefold()))
    total = int(_binding_value(total_result["results"]["bindings"][0], "total"))

    return {
        "total_individuals": total,
        "typed_classes": len(counts),
        "type_distribution": counts[:DASHBOARD_TYPE_LIMIT],
        "modules": modules,
        "available": True,
    }


def knowledge_graph(
    class_name: str = "",
    service: SparqlService | None = None,
) -> dict[str, Any]:
    modules = list_modules()
    class_by_name = {
        item.local_name: item
        for module in modules
        for item in module.classes
    }
    classes = [item for module in modules for item in module.classes]
    if class_name:
        module = next((item for item in modules if class_name in item.classes_by_name), None)
        if module is None:
            raise ValueError("Unknown ontology class.")
        classes = [
            module.classes_by_name[name.rsplit("#", 1)[-1]]
            for name in module.subtree_iris(class_name)
        ]

    query = f"""
        SELECT DISTINCT ?subject ?type ?predicate ?object
        WHERE {{
          VALUES ?type {{ {_iri_values(classes)} }}
          ?subject a ?type .
          OPTIONAL {{
            ?subject ?predicate ?object .
            FILTER(?predicate != <{_RDF_TYPE}>)
          }}
        }}
        LIMIT {GRAPH_TRIPLE_LIMIT}
        """
    payload = (service or SparqlService()).select(query)
    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[tuple[str, str, str], dict[str, Any]] = {}
    bindings = payload["results"]["bindings"]

    for binding in bindings:
        subject = _binding_term(binding, "subject")
        type_iri = _binding_value(binding, "type")
        if subject is None or not subject["value"].startswith(ONTOLOGY_NS):
            continue
        subject_iri = subject["value"]
        subject_class = class_by_name.get(type_iri.rsplit("#", 1)[-1])
        nodes.setdefault(
            subject_iri,
            _node(subject_iri, _local_label(subject_iri), "individual", subject_class),
        )
        type_class = class_by_name.get(type_iri.rsplit("#", 1)[-1])
        if type_class is not None:
            nodes.setdefault(type_iri, _node(type_iri, type_class.display_name, "class", type_class))
            _add_edge(edges, subject_iri, type_iri, _RDF_TYPE, "type")

        predicate = _binding_value(binding, "predicate")
        object_term = _binding_term(binding, "object")
        if not predicate or object_term is None:
            continue
        if object_term.get("type") == "uri":
            object_iri = object_term["value"]
            object_class = class_by_name.get(object_iri.rsplit("#", 1)[-1])
            nodes.setdefault(
                object_iri,
                _node(object_iri, _local_label(object_iri), "class" if object_class else "resource", object_class),
            )
        elif object_term.get("type") == "literal":
            object_iri = _literal_id(object_term)
            nodes.setdefault(
                object_iri,
                {
                    "data": {
                        "id": object_iri,
                        "label": _shorten(object_term.get("value", "")),
                        "kind": "literal",
                        "detail": object_term.get("datatype") or object_term.get("xml:lang", "Literal"),
                    }
                },
            )
        else:
            continue
        _add_edge(edges, subject_iri, object_iri, predicate, _local_label(predicate))

    return {
        "nodes": list(nodes.values()),
        "edges": list(edges.values()),
        "truncated": len(bindings) >= GRAPH_TRIPLE_LIMIT,
        "limit": GRAPH_TRIPLE_LIMIT,
    }


def _iri_values(classes: list[OntologyClass]) -> str:
    return " ".join(f"<{item.iri}>" for item in classes)


def _binding_value(binding: dict[str, Any], name: str) -> str:
    term = binding.get(name)
    return term.get("value", "") if isinstance(term, dict) else ""


def _binding_term(binding: dict[str, Any], name: str) -> dict[str, Any] | None:
    term = binding.get(name)
    return term if isinstance(term, dict) and isinstance(term.get("value"), str) else None


def _node(
    iri: str, label: str, kind: str, ontology_class: OntologyClass | None
) -> dict[str, Any]:
    return {
        "data": {
            "id": iri,
            "label": _shorten(label),
            "kind": kind,
            "class": ontology_class.display_name if ontology_class else "",
            "detail": iri,
        }
    }


def _add_edge(
    edges: dict[tuple[str, str, str], dict[str, Any]],
    source: str,
    target: str,
    predicate: str,
    label: str,
) -> None:
    key = (source, predicate, target)
    if key not in edges:
        edges[key] = {
            "data": {
                "id": f"edge-{len(edges)}",
                "source": source,
                "target": target,
                "label": _shorten(label),
                "predicate": predicate,
            }
        }


def _literal_id(term: dict[str, Any]) -> str:
    language = term.get("xml:lang", "")
    datatype = term.get("datatype", "")
    return f"literal:{language}:{datatype}:{term.get('value', '')}"


def _local_label(iri: str) -> str:
    return iri.rsplit("#", 1)[-1].rsplit("/", 1)[-1]


def _shorten(value: str, limit: int = 96) -> str:
    return value if len(value) <= limit else f"{value[: limit - 1]}…"
