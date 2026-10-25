"""Natural-language question page."""

from __future__ import annotations

import logging

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from web_sem.nlp.forms import QuestionForm
from web_sem.nlp.service import SAMPLE_QUESTIONS, Answer, answer_question
from web_sem.ontology import OntologyError

logger = logging.getLogger(__name__)


@require_http_methods(["GET"])
def questions(request: HttpRequest) -> HttpResponse:
    form = QuestionForm(request.GET or None)
    answer = None
    status = 200
    if "q" in request.GET and form.is_valid():
        try:
            answer = answer_question(form.cleaned_data["q"])
        except OntologyError:
            logger.exception("Ontology is unavailable for a question")
            answer = Answer(
                question=form.cleaned_data["q"],
                error="The ontology could not be read.",
                http_status=503,
            )
        status = answer.http_status
    return render(
        request,
        "nlp/question.html",
        {
            "active": "questions",
            "form": form,
            "answer": answer,
            "samples": SAMPLE_QUESTIONS,
        },
        status=status,
    )
