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


class IndividualForm(forms.Form):
    module_root = ""

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
