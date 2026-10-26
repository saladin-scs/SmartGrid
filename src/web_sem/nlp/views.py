"""Natural-language question page."""

from __future__ import annotations

import hashlib
import hmac
import logging
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from web_sem.nlp.creation import (
    CreationError,
    CreationPreview,
    persist_creation,
    prepare_creation,
)
from web_sem.nlp.creation_forms import EntityCreationForm
from web_sem.nlp.forms import QuestionForm
from web_sem.nlp.service import SAMPLE_QUESTIONS, Answer, answer_question
from web_sem.ontology import OntologyError
from web_sem.repository import IndividualRepository
from web_sem.sparql import SparqlServiceError

logger = logging.getLogger(__name__)
_CREATION_PREVIEW_SESSION_KEY = "natural_language_creation_preview"


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


@require_http_methods(["GET", "POST"])
def create_entity(request: HttpRequest) -> HttpResponse:
    form = EntityCreationForm(request.POST or None)
    preview: CreationPreview | None = None
    status = 200

    if request.method == "POST" and form.is_valid():
        action = request.POST.get("action", "")
        if action not in {"preview", "confirm"}:
            form.add_error(None, "Choisissez la prévisualisation ou la confirmation.")
        elif action == "preview":
            request.session.pop(_CREATION_PREVIEW_SESSION_KEY, None)
            preview, status = _prepare_entity_preview(request, form)
        else:
            if settings.USE_MOCK_RDF:
                form.add_error(
                    None,
                    "La création naturelle nécessite Fuseki. Désactivez USE_MOCK_RDF pour écrire dans le jeu energy.",
                )
            else:
                description = form.cleaned_data["description"]
                expected = request.session.get(_CREATION_PREVIEW_SESSION_KEY, "")
                confirmation_key = hashlib.sha256(description.encode("utf-8")).hexdigest()
                if not expected or not hmac.compare_digest(expected, confirmation_key):
                    request.session.pop(_CREATION_PREVIEW_SESSION_KEY, None)
                    form.add_error(
                        None,
                        "Prévisualisez d’abord cette description avant de confirmer son insertion.",
                    )
                else:
                    try:
                        preview = prepare_creation(description, IndividualRepository())
                    except CreationError as exc:
                        form.add_error("description", str(exc))
                    except (OntologyError, SparqlServiceError):
                        logger.exception("Could not prepare the natural-language RDF individual")
                        form.add_error(
                            None,
                            "L’ontologie ou le serveur Fuseki est indisponible. Aucun triple n’a été écrit.",
                        )
                        status = 503
                    else:
                        if not form.cleaned_data["confirmed"]:
                            form.add_error(None, "Cochez la confirmation avant toute insertion RDF.")
                        else:
                            request.session.pop(_CREATION_PREVIEW_SESSION_KEY, None)
                            try:
                                persist_creation(preview, IndividualRepository())
                            except CreationError as exc:
                                preview = None
                                form.add_error(None, str(exc))
                            except (OntologyError, SparqlServiceError):
                                logger.exception("Fuseki rejected the confirmed RDF insertion")
                                preview = None
                                form.add_error(
                                    None,
                                    "Fuseki n’a pas confirmé l’insertion. Aucun succès n’est affiché.",
                                )
                                status = 503
                            else:
                                messages.success(
                                    request,
                                    f"L’individu « {preview.local_name} » a été inséré dans le jeu RDF energy.",
                                )
                                query = urlencode({"rdf_type": preview.class_name})
                                return redirect(f"{reverse(preview.module.list_url_name)}?{query}")

    return render(
        request,
        "nlp/create_entity.html",
        {
            "active": "creation",
            "form": form,
            "preview": preview,
        },
        status=status,
    )


def _prepare_entity_preview(
    request: HttpRequest, form: EntityCreationForm
) -> tuple[CreationPreview | None, int]:
    if settings.USE_MOCK_RDF:
        form.add_error(
            None,
            "La création naturelle nécessite Fuseki. Désactivez USE_MOCK_RDF pour écrire dans le jeu energy.",
        )
        return None, 503
    try:
        preview = prepare_creation(form.cleaned_data["description"], IndividualRepository())
    except CreationError as exc:
        form.add_error("description", str(exc))
        return None, 200
    except (OntologyError, SparqlServiceError):
        logger.exception("Could not prepare the natural-language RDF individual")
        form.add_error(
            None,
            "L’ontologie ou le serveur Fuseki est indisponible. Aucun triple n’a été écrit.",
        )
        return None, 503
    else:
        request.session[_CREATION_PREVIEW_SESSION_KEY] = hashlib.sha256(
            form.cleaned_data["description"].encode("utf-8")
        ).hexdigest()
        return preview, 200
