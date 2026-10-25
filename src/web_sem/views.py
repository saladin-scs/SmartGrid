"""Shared CRUD views. Each ontology module supplies its own forms."""

from __future__ import annotations

import logging

from django.contrib import messages
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from web_sem.forms import IndividualForm, IndividualSearchForm
from web_sem.ontology import OntologyError, get_module, individual_iri, list_modules
from web_sem.repository import IndividualRepository
from web_sem.sparql import SparqlServiceError

logger = logging.getLogger(__name__)


def rdf_page(view):
    def wrapper(request: HttpRequest, *args, **kwargs) -> HttpResponse:
        try:
            return view(request, *args, **kwargs)
        except OntologyError as exc:
            return _unavailable(request, exc)
        except SparqlServiceError as exc:
            return _unavailable(request, exc)

    return wrapper


def home(request: HttpRequest) -> HttpResponse:
    try:
        modules = list_modules()
    except OntologyError as exc:
        return _unavailable(request, exc)
    return render(request, "home.html", {"modules": modules, "active": "home"})


@rdf_page
@require_http_methods(["GET"])
def individual_list(request: HttpRequest, search_form_class: type[IndividualSearchForm]) -> HttpResponse:
    module = get_module(search_form_class.module_root)
    search_form = search_form_class(request.GET)
    individuals = []
    if search_form.is_valid():
        individuals = IndividualRepository().list_individuals(
            module,
            query=search_form.cleaned_data["q"],
            class_name=search_form.cleaned_data["rdf_type"],
        )
    return render(
        request,
        "individuals/list.html",
        {
            "module": module,
            "active": module.key,
            "search_form": search_form,
            "individuals": individuals,
        },
    )


@rdf_page
@require_http_methods(["GET"])
def individual_detail(
    request: HttpRequest,
    local_name: str,
    form_class: type[IndividualForm],
) -> HttpResponse:
    module = get_module(form_class.module_root)
    individual = _get_or_404(module, local_name)
    return render(
        request,
        "individuals/detail.html",
        {"module": module, "active": module.key, "individual": individual},
    )


@rdf_page
@require_http_methods(["GET", "POST"])
def individual_create(request: HttpRequest, form_class: type[IndividualForm]) -> HttpResponse:
    module = get_module(form_class.module_root)
    form = form_class(request.POST or None)
    if request.method == "POST" and form.is_valid():
        name = form.cleaned_data["local_name"]
        try:
            IndividualRepository().create(module, name, form.cleaned_data["rdf_type"])
        except SparqlServiceError:
            logger.exception("Could not create RDF individual")
            form.add_error(None, "The RDF store could not save this individual.")
        else:
            messages.success(request, f"Created {name}.")
            return redirect(module.detail_url_name, name)
    return render(
        request,
        "individuals/form.html",
        {
            "module": module,
            "active": module.key,
            "form": form,
            "page_title": f"New {module.root}",
            "cancel_url": reverse(module.list_url_name),
            "individual": None,
        },
    )


@rdf_page
@require_http_methods(["GET", "POST"])
def individual_edit(
    request: HttpRequest,
    local_name: str,
    form_class: type[IndividualForm],
) -> HttpResponse:
    module = get_module(form_class.module_root)
    individual = _get_or_404(module, local_name)
    form = form_class(
        request.POST or None,
        editing=True,
        initial={"rdf_type": individual.class_name},
    )
    if request.method == "POST" and form.is_valid():
        try:
            IndividualRepository().update_class(
                module,
                individual.local_name,
                form.cleaned_data["rdf_type"],
            )
        except SparqlServiceError:
            logger.exception("Could not update RDF individual")
            form.add_error(None, "The RDF store could not save this individual.")
        else:
            messages.success(request, f"Updated {individual.local_name}.")
            return redirect(module.detail_url_name, individual.local_name)
    return render(
        request,
        "individuals/form.html",
        {
            "module": module,
            "active": module.key,
            "form": form,
            "page_title": f"Edit {individual.local_name}",
            "cancel_url": reverse(module.detail_url_name, args=[individual.local_name]),
            "individual": individual,
        },
    )


@rdf_page
@require_http_methods(["GET", "POST"])
def individual_delete(
    request: HttpRequest,
    local_name: str,
    form_class: type[IndividualForm],
) -> HttpResponse:
    module = get_module(form_class.module_root)
    individual = _get_or_404(module, local_name)
    if request.method == "POST":
        try:
            IndividualRepository().delete(individual.local_name)
        except SparqlServiceError as exc:
            return _unavailable(request, exc)
        messages.success(request, f"Deleted {individual.local_name}.")
        return redirect(module.list_url_name)
    return render(
        request,
        "individuals/delete.html",
        {"module": module, "active": module.key, "individual": individual},
    )


def _get_or_404(module, local_name: str):
    try:
        individual_iri(local_name)
    except ValueError as exc:
        raise Http404("Individual name is not valid.") from exc
    individual = IndividualRepository().get(module, local_name)
    if individual is None:
        raise Http404("Individual was not found in this module.")
    return individual


def _unavailable(request: HttpRequest, exc: Exception) -> HttpResponse:
    logger.exception("RDF request failed")
    return render(
        request,
        "individuals/unavailable.html",
        {"message": str(exc), "active": ""},
        status=503,
    )
