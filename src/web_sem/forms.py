"""Forms for RDF individuals. SPARQL stays in the repository."""

from __future__ import annotations

from django import forms

from web_sem.nlp import prepare_individual_name
from web_sem.ontology import (
    LOCAL_NAME_RE,
    MAX_LOCAL_NAME,
    OntologyModule,
    get_module,
    reserved_names,
)
from web_sem.repository import IndividualRepository
from web_sem.sparql import SparqlServiceError


class IndividualSearchForm(forms.Form):
    module_root = ""

    q = forms.CharField(
        required=False,
        label="Nom",
        max_length=MAX_LOCAL_NAME,
        widget=forms.TextInput(attrs={"class": "control"}),
    )

    def __init__(self, *args, **kwargs) -> None:
        self.module: OntologyModule = get_module(self.module_root)
        super().__init__(*args, **kwargs)
        self.fields["rdf_type"] = forms.ChoiceField(
            required=False,
            label="Classe",
            choices=[("", "Toutes les classes"), *self.module.choice_tuples()],
            widget=forms.Select(attrs={"class": "control"}),
        )

    def clean_q(self) -> str:
        return self.cleaned_data["q"].strip()

    def clean_rdf_type(self) -> str:
        value = self.cleaned_data["rdf_type"]
        if value and value not in self.module.classes_by_name:
            raise forms.ValidationError("Choisissez une classe de ce domaine.")
        return value


class PropertyField:
    """A property edited next to the class: a literal (text/decimal/email) or a link."""

    def __init__(
        self,
        name,
        label,
        *,
        kind="text",
        required=False,
        ref_root="",
        ref_class="",
        only_classes=(),
        help_text="",
    ):
        self.name = name
        self.label = label
        self.kind = kind
        self.required = required
        self.ref_root = ref_root
        self.ref_class = ref_class
        self.only_classes = tuple(only_classes)
        self.help_text = help_text


class IndividualForm(forms.Form):
    module_root = ""
    property_fields: tuple[PropertyField, ...] = ()

    def __init__(self, *args, editing: bool = False, **kwargs) -> None:
        self.module = get_module(self.module_root)
        self.editing = editing
        super().__init__(*args, **kwargs)
        if not editing:
            self.fields["local_name"] = forms.CharField(
                label="Nom de l’individu",
                max_length=MAX_LOCAL_NAME,
                help_text=(
                    "Nom local de l’individu RDF. Il devient la partie finale de l’IRI "
                    "et ne correspond pas à une propriété de l’ontologie."
                ),
                widget=forms.TextInput(attrs={"class": "control", "autocomplete": "off"}),
            )
        self.fields["rdf_type"] = forms.ChoiceField(
            label="Classe",
            choices=self.module.choice_tuples(),
            help_text="Classe existante de l’ontologie ajoutée avec rdf:type.",
            widget=forms.Select(attrs={"class": "control"}),
        )
        for spec in self.property_fields:
            self.fields[f"prop_{spec.name}"] = self._build_field(spec)

    def _build_field(self, spec: PropertyField) -> forms.Field:
        attrs = {"class": "control"}
        common = {"label": spec.label, "required": spec.required, "help_text": spec.help_text}
        if spec.kind == "ref":
            choices = [("", "— Aucun —")] + [
                (n, n) for n in self._reference_names(spec.ref_root, spec.ref_class)
            ]
            return forms.ChoiceField(choices=choices, widget=forms.Select(attrs=attrs), **common)
        if spec.kind == "decimal":
            return forms.DecimalField(
                min_value=0,
                decimal_places=3,
                widget=forms.NumberInput(attrs={**attrs, "step": "any"}),
                **common,
            )
        if spec.kind == "email":
            return forms.EmailField(max_length=120, widget=forms.EmailInput(attrs=attrs), **common)
        if spec.kind == "date":
            return forms.CharField(max_length=20, widget=forms.TextInput(attrs={**attrs, "type": "date"}), **common)
        return forms.CharField(max_length=120, widget=forms.TextInput(attrs=attrs), **common)

    @staticmethod
    def _reference_names(root: str, class_name: str = "") -> list[str]:
        try:
            return [
                i.local_name
                for i in IndividualRepository().list_individuals(
                    get_module(root),
                    class_name=class_name,
                )
            ]
        except SparqlServiceError:
            return []

    def clean(self):
        cleaned = super().clean()
        rdf_type = cleaned.get("rdf_type")
        if rdf_type:
            for spec in self.property_fields:
                key = f"prop_{spec.name}"
                if not spec.only_classes or cleaned.get(key) in (None, ""):
                    continue
                if not any(_descends(self.module, rdf_type, root) for root in spec.only_classes):
                    shown = self.module.classes_by_name[rdf_type].display_name
                    self.add_error(key, f"Cette propriété ne s’applique pas à la classe {shown}.")
        return cleaned

    def property_values(self) -> dict[str, str]:
        return {
            spec.name: str(self.cleaned_data.get(f"prop_{spec.name}") or "")
            for spec in self.property_fields
        }

    def set_initial_properties(self, values: dict[str, str]) -> None:
        for spec in self.property_fields:
            if spec.name in values:
                self.initial[f"prop_{spec.name}"] = values[spec.name]

    def clean_local_name(self) -> str:
        name = prepare_individual_name(self.cleaned_data["local_name"])
        if not LOCAL_NAME_RE.fullmatch(name) or len(name) > MAX_LOCAL_NAME:
            raise forms.ValidationError(
                "Utilisez des lettres, des chiffres ou des traits de soulignement, en commençant par une lettre."
            )
        if name in reserved_names():
            raise forms.ValidationError(
                "Ce nom correspond à une classe ou propriété de l’ontologie, pas à un individu."
            )
        try:
            if IndividualRepository().exists(name):
                raise forms.ValidationError("Un individu RDF portant ce nom existe déjà.")
        except SparqlServiceError as exc:
            raise forms.ValidationError("Le magasin RDF n’est pas joignable.") from exc
        return name

    def clean_rdf_type(self) -> str:
        value = self.cleaned_data["rdf_type"]
        if value not in self.module.classes_by_name:
            raise forms.ValidationError("Choisissez une classe de ce domaine.")
        return value


def _descends(module: OntologyModule, name: str, ancestor: str) -> bool:
    while name:
        if name == ancestor:
            return True
        name = module.classes_by_name[name].parent
    return False
