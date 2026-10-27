"""Class lookups limited to SourceProduction and Stockage."""

from __future__ import annotations

from web_sem.ontology import OntologyClass, OntologyModule, list_modules


def locate(local_name: str) -> tuple[OntologyModule, OntologyClass] | None:
    for module in list_modules():
        item = module.classes_by_name.get(local_name)
        if item is not None:
            return module, item
    return None


def is_root(local_name: str) -> bool:
    found = locate(local_name)
    return found is not None and found[1].depth == 0


def subtree_names(local_name: str) -> list[str]:
    """Return a class and its descendants in ontology order."""
    found = locate(local_name)
    if found is None:
        return []
    module, _item = found
    selected = set(module.subtree_iris(local_name))
    return [item.local_name for item in module.classes if item.iri in selected]


def relation_properties(local_name: str) -> tuple[str, ...]:
    """Properties that link an individual of this class to a Zone.

    People are linked with estAffecteA (staff) or residentDans (clients);
    installation sites are linked to their city with appartientAVille.
    An empty tuple means the class has no zone relation.
    """
    found = locate(local_name)
    if found is None:
        return ()
    module, _item = found
    if module.root == "Personne":
        return ("estAffecteA", "residentDans")
    if module.root == "Zone" and (local_name == "SiteInstallation" or is_ancestor("SiteInstallation", local_name)):
        return ("appartientAVille",)
    return ()


def all_class_names() -> list[str]:
    names: list[str] = []
    for module in list_modules():
        names.extend(item.local_name for item in module.classes)
    return names


def known_names() -> set[str]:
    return set(all_class_names())


def is_ancestor(ancestor: str, descendant: str) -> bool:
    found = locate(descendant)
    if found is None:
        return False
    module, current = found
    seen: set[str] = set()
    while current.parent and current.parent not in seen:
        if current.parent == ancestor:
            return True
        seen.add(current.parent)
        parent = module.classes_by_name.get(current.parent)
        if parent is None:
            return False
        current = parent
    return False
