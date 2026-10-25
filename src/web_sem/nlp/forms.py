"""Question form. SPARQL is not a field."""

from __future__ import annotations

from django import forms

from web_sem.nlp.interpret import MAX_QUESTION


class QuestionForm(forms.Form):
    q = forms.CharField(
        label="Question",
        max_length=MAX_QUESTION,
        widget=forms.Textarea(attrs={"rows": 4, "class": "control"}),
        help_text=(
            "Ask in French or English about production, storage, consumers, or contracts. "
            "The text is not executed as SPARQL."
        ),
    )

    def clean_q(self) -> str:
        return " ".join(self.cleaned_data["q"].split())
