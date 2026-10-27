"""Shared CRUD views. Each ontology module supplies its own forms."""

from __future__ import annotations

import logging
from dataclasses import replace

from django.contrib import messages
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods

from web_sem.forms import IndividualForm, IndividualSearchForm
from web_sem.intelligence import GRAPH_TRIPLE_LIMIT, dashboard_summary, knowledge_graph
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
    return render(request, "home.html", {"modules": modules, "active": "public"})


@require_GET
def overview(request: HttpRequest) -> HttpResponse:
    summary = None
    status = 200
    try:
        summary = dashboard_summary()
    except (OntologyError, SparqlServiceError):
        logger.exception("Could not load the SmartGrid overview from Fuseki")
        status = 503
    return render(
        request,
        "intelligence/overview.html",
        {"active": "overview", "summary": summary, "store_available": summary is not None},
        status=status,
    )


@require_GET
def graph_explorer(request: HttpRequest) -> HttpResponse:
    try:
        modules = list_modules()
    except OntologyError:
        logger.exception("Could not load ontology classes for the graph explorer")
        return render(
            request,
            "individuals/unavailable.html",
            {
                "message": "L’ontologie ENERGIE.rdf n’est pas disponible.",
                "active": "graph",
            },
            status=503,
        )
    classes = [item for module in modules for item in module.classes]
    return render(
        request,
        "intelligence/graph.html",
        {
            "active": "graph",
            "ontology_classes": classes,
            "graph_triple_limit": GRAPH_TRIPLE_LIMIT,
        },
    )


@require_GET
def graph_data(request: HttpRequest) -> JsonResponse:
    class_name = request.GET.get("class", "").strip()
    try:
        payload = knowledge_graph(class_name)
    except ValueError:
        return JsonResponse({"error": "Classe de l’ontologie inconnue."}, status=400)
    except (OntologyError, SparqlServiceError):
        logger.exception("Could not retrieve graph data from Fuseki")
        return JsonResponse(
            {"error": "Fuseki ou l’ontologie est indisponible."},
            status=503,
        )
    return JsonResponse(payload)


@rdf_page
@require_http_methods(["GET"])
def individual_list(request: HttpRequest, search_form_class: type[IndividualSearchForm]) -> HttpResponse:
    module = get_module(search_form_class.module_root)
    search_form = search_form_class(request.GET)
    individuals = []
    if search_form.is_valid():
        repository = IndividualRepository()
        individuals = repository.list_individuals(
            module,
            query=search_form.cleaned_data["q"],
            class_name=search_form.cleaned_data["rdf_type"],
        )
        if module.key in WITH_SUMMARY:
            summary = repository.property_summary()
            individuals = [replace(item, properties=summary.get(item.local_name, ())) for item in individuals]
    return render(
        request,
        "individuals/list.html",
        {
            "module": module,
            "active": module.key,
            "search_form": search_form,
            "individuals": individuals,
            "class_counts": _class_counts(module, individuals),
            "with_summary": module.key in WITH_SUMMARY,
        },
    )


# Modules whose list shows a name and a zone next to each individual.
WITH_SUMMARY = frozenset({"personne", "zone", "evenement", "capteur_dispositif"})


def _class_counts(module, individuals) -> list[dict]:
    """How many listed individuals each class has, in ontology order."""
    counts: dict[str, int] = {}
    for item in individuals:
        counts[item.class_name] = counts.get(item.class_name, 0) + 1
    return [
        {"name": ontology_class.local_name, "label": ontology_class.display_name, "count": counts[ontology_class.local_name]}
        for ontology_class in module.classes
        if ontology_class.local_name in counts
    ]


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
            IndividualRepository().create(
                module, name, form.cleaned_data["rdf_type"], form.property_values()
            )
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
    form.set_initial_properties(individual.property_map())
    if request.method == "POST" and form.is_valid():
        try:
            repository = IndividualRepository()
            repository.update_class(
                module,
                individual.local_name,
                form.cleaned_data["rdf_type"],
            )
            if form.property_fields:
                repository.set_properties(individual.local_name, form.property_values())
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


@require_GET
def scenario_list(request: HttpRequest) -> HttpResponse:
    from web_sem.scenarios import SCENARIOS

    return render(request, "scenarios/list.html", {"scenarios": SCENARIOS, "active": "scenarios"})


@require_GET
def scenario_run(request: HttpRequest, key: str) -> HttpResponse:
    from web_sem import scenarios

    scenario = scenarios.BY_KEY.get(key)
    if scenario is None:
        raise Http404("Unknown scenario.")
    value = request.GET.get("value", "").strip()
    context = {
        "scenario": scenario,
        "active": "scenarios",
        "value": value,
        "choices": [],
        "rows": [],
        "query": "",
        "error": "",
        "ready": False,
    }
    status = 200
    try:
        if scenario.param:
            context["choices"] = scenarios.param_choices(scenario)
        if not scenario.param or value:
            if scenario.param and value not in context["choices"]:
                context["error"] = "Choisissez un individu de la liste."
                status = 400
            else:
                context["query"], context["rows"] = scenarios.run(scenario, value)
                context["ready"] = True
    except (OntologyError, SparqlServiceError):
        logger.exception("Scenario %s failed", key)
        context["error"] = "Fuseki ou l’ontologie est indisponible."
        status = 503
    return render(request, "scenarios/run.html", context, status=status)
