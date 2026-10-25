"""Template context shared by the module navigation."""

from web_sem.ontology import OntologyError, list_modules


def navigation(request):
    try:
        modules = list_modules()
    except OntologyError:
        modules = ()
    return {"ontology_modules": modules}
