"""Forms for the confirmed natural-language RDF creation flow."""

from __future__ import annotations

from django import forms

from web_sem.nlp.interpret import MAX_QUESTION


class EntityCreationForm(forms.Form):
    description = forms.CharField(
        label="Décrivez l’individu en français",
        max_length=MAX_QUESTION,
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "class": "control",
                "placeholder": "Créer une centrale solaire appelée CentraleSud.",
            }
        ),
        help_text=(
            "Indiquez une classe de l’ontologie et un nom avec « appelé(e) » ou « nommé(e) ». "
            "Les propriétés doivent être explicites, par exemple nomPersonne=Amal."
        ),
    )
    confirmed = forms.BooleanField(
        required=False,
        label="Je confirme l’insertion des triples RDF affichés.",
    )

    def clean_description(self) -> str:
        return " ".join(self.cleaned_data["description"].split())
