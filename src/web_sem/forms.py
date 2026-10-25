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
        label="Name",
        max_length=MAX_LOCAL_NAME,
        widget=forms.TextInput(attrs={"class": "control"}),
    )

    def __init__(self, *args, **kwargs) -> None:
        self.module: OntologyModule = get_module(self.module_root)
        super().__init__(*args, **kwargs)
        self.fields["rdf_type"] = forms.ChoiceField(
            required=False,
            label="Class",
            choices=[("", "All classes"), *self.module.choice_tuples()],
            widget=forms.Select(attrs={"class": "control"}),
        )

    def clean_q(self) -> str:
        return self.cleaned_data["q"].strip()

    def clean_rdf_type(self) -> str:
        value = self.cleaned_data["rdf_type"]
        if value and value not in self.module.classes_by_name:
            raise forms.ValidationError("Choose a class from this module.")
        return value


class IndividualForm(forms.Form):
    module_root = ""

    def __init__(self, *args, editing: bool = False, **kwargs) -> None:
        self.module = get_module(self.module_root)
        self.editing = editing
        super().__init__(*args, **kwargs)
        if not editing:
            self.fields["local_name"] = forms.CharField(
                label="Individual name",
                max_length=MAX_LOCAL_NAME,
                help_text=(
                    "Local name of the RDF individual. It becomes the IRI fragment "
                    "and is not an ontology property."
                ),
                widget=forms.TextInput(attrs={"class": "control", "autocomplete": "off"}),
            )
        self.fields["rdf_type"] = forms.ChoiceField(
            label="Class",
            choices=self.module.choice_tuples(),
            help_text="Existing ontology class asserted with rdf:type.",
            widget=forms.Select(attrs={"class": "control"}),
        )

    def clean_local_name(self) -> str:
        name = prepare_individual_name(self.cleaned_data["local_name"])
        if not LOCAL_NAME_RE.fullmatch(name) or len(name) > MAX_LOCAL_NAME:
            raise forms.ValidationError(
                "Use letters, digits, and underscores, and start with a letter."
            )
        if name in reserved_names():
            raise forms.ValidationError(
                "This name is an ontology class or property, not an individual."
            )
        try:
            if IndividualRepository().exists(name):
                raise forms.ValidationError("An RDF individual with this name already exists.")
        except SparqlServiceError as exc:
            raise forms.ValidationError("The RDF store could not be reached.") from exc
        return name

    def clean_rdf_type(self) -> str:
        value = self.cleaned_data["rdf_type"]
        if value not in self.module.classes_by_name:
            raise forms.ValidationError("Choose a class from this module.")
        return value
