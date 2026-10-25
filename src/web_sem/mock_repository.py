import json
from pathlib import Path
from django.conf import settings
from .ontology import ONTOLOGY_NS, individual_iri, OntologyModule
from .repository import Individual

class MockIndividualRepository:
    def __init__(self) -> None:
        self.path = settings.BASE_DIR / "data" / "mock_individuals.json"
        self._ensure_file()

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
        )

    def exists(self, local_name: str) -> bool:
        return local_name in self._load()

    def create(self, module: OntologyModule, local_name: str, class_name: str) -> None:
        data = self._load()
        data[local_name] = class_name
        self._save(data)

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
