"""Question form. SPARQL is not a field."""

from __future__ import annotations

from django import forms

from web_sem.nlp.interpret import MAX_QUESTION


class QuestionForm(forms.Form):
    q = forms.CharField(
        label="Votre question",
        max_length=MAX_QUESTION,
        widget=forms.Textarea(attrs={"rows": 4, "class": "control"}),
        help_text=(
            "Interrogez en français les sources de production, les stockages, les consommateurs "
            "ou les contrats. Votre texte n’est jamais exécuté comme du SPARQL."
        ),
    )

    def clean_q(self) -> str:
        return " ".join(self.cleaned_data["q"].split())
