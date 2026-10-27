import json
from pathlib import Path
from django.conf import settings
from .ontology import ONTOLOGY_NS, individual_iri, OntologyModule
from .ontology import get_property
from .repository import Individual, PropertyValue

class MockIndividualRepository:
    def __init__(self) -> None:
        self.path = settings.BASE_DIR / "data" / "mock_individuals.json"
        self.props_path = self.path.with_name("mock_properties.json")
        self._ensure_file()

    def _load_props(self) -> dict[str, dict[str, str]]:
        if not self.props_path.exists():
            return {}
        with open(self.props_path, "r") as f:
            return json.load(f)

    def _save_props(self, data: dict[str, dict[str, str]]) -> None:
        with open(self.props_path, "w") as f:
            json.dump(data, f, indent=2)

    def properties_of(self, local_name: str) -> tuple[PropertyValue, ...]:
        items = []
        for name, value in sorted(self._load_props().get(local_name, {}).items()):
            prop = get_property(name)
            items.append(PropertyValue(name, value, bool(prop and prop.is_object)))
        return tuple(items)

    def incoming_of(self, local_name: str) -> tuple[PropertyValue, ...]:
        found = []
        for subject, props in sorted(self._load_props().items()):
            for name, value in sorted(props.items()):
                prop = get_property(name)
                if prop and prop.is_object and value == local_name:
                    found.append(PropertyValue(name, subject, True))
        return tuple(found)

    def set_properties(self, local_name: str, values: dict[str, str]) -> None:
        data = self._load_props()
        current = data.setdefault(local_name, {})
        for name, value in values.items():
            if (value or "").strip():
                current[name] = value.strip()
            else:
                current.pop(name, None)
        self._save_props(data)

    def _ensure_file(self) -> None:
        if not self.path.exists():
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "w") as f:
                json.dump({}, f)

    def _load(self) -> dict[str, str]:
        with open(self.path, "r") as f:
            return json.load(f)

    def _save(self, data: dict[str, str]) -> None:
        with open(self.path, "w") as f:
            json.dump(data, f, indent=2)

    def list_individuals(
        self,
        module: OntologyModule,
        *,
        query: str = "",
        class_name: str = "",
    ) -> list[Individual]:
        data = self._load()
        individuals = []
        
        subtree_iris = set(module.subtree_iris(class_name or None))
        
        for name, cls_name in data.items():
            if query and query.lower() not in name.lower():
                continue
            
            iri = individual_iri(name)
            cls_iri = module.classes_by_name[cls_name].iri if cls_name in module.classes_by_name else None
            
            if cls_iri and cls_iri in subtree_iris:
                individuals.append(
                    Individual(
                        local_name=name,
                        iri=iri,
                        class_name=cls_name,
                        class_display=module.classes_by_name[cls_name].display_name,
                        hierarchy=module.hierarchy(cls_name),
                    )
                )
        
        return sorted(individuals, key=lambda x: x.local_name.lower())

    def get(self, module: OntologyModule, local_name: str) -> Individual | None:
        data = self._load()
        if local_name not in data:
            return None
        
        cls_name = data[local_name]
        if cls_name not in module.classes_by_name:
            return None
            
        return Individual(
            local_name=local_name,
            iri=individual_iri(local_name),
            class_name=cls_name,
            class_display=module.classes_by_name[cls_name].display_name,
            hierarchy=module.hierarchy(cls_name),
            properties=self.properties_of(local_name),
            incoming=self.incoming_of(local_name),
        )

    def exists(self, local_name: str) -> bool:
        return local_name in self._load()

    def create(
        self,
        module: OntologyModule,
        local_name: str,
        class_name: str,
        properties: dict[str, str] | None = None,
    ) -> None:
        data = self._load()
        data[local_name] = class_name
        self._save(data)
        if properties:
            self.set_properties(local_name, properties)

    def update_class(self, module: OntologyModule, local_name: str, class_name: str) -> None:
        data = self._load()
        if local_name in data:
            data[local_name] = class_name
            self._save(data)

    def delete(self, local_name: str) -> None:
        data = self._load()
        if local_name in data:
            del data[local_name]
            self._save(data)
        props = self._load_props()
        if props.pop(local_name, None) is not None:
            self._save_props(props)
