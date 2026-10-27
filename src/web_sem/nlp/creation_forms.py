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
                "placeholder": "Créer un véhicule lourd vehi1, sans ville ni zone.",
            }
        ),
        help_text=(
            "Décrivez librement l’individu, sa classe et ses attributs. "
            "Exemple : « Créer un véhicule lourd vehi1, sans ville ni zone. » "
            "La ville et la zone sont facultatives."
        ),
    )
    confirmed = forms.BooleanField(
        required=False,
        label="Je confirme l’insertion des triples RDF affichés.",
    )

    def clean_description(self) -> str:
        return " ".join(self.cleaned_data["description"].split())
