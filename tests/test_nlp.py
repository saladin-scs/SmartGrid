"""NLP intents, read-only SPARQL, and the question page."""

from __future__ import annotations

import pytest
from django.urls import reverse

from web_sem.nlp import prepare_individual_name
from web_sem.nlp.aliases import alias_index
from web_sem.nlp.forms import QuestionForm
from web_sem.nlp.normalize import normalize, normalized_question
from web_sem.nlp.service import SAMPLE_QUESTIONS, Answer, answer_question
from web_sem.nlp.sparql import QueryRejected, validate_select
from web_sem.ontology import class_iri, get_module, individual_iri, list_modules
from web_sem.sparql import SparqlService

EXAMPLES = [
    ("Quelles sources de production existent ?", "LIST_INDIVIDUALS", "SourceProduction", "fr"),
    ("Liste les centrales nucléaires.", "FILTER_BY_CLASS", "CentraleNucleaire", "fr"),
    ("Liste les centrales nucleaires.", "FILTER_BY_CLASS", "CentraleNucleaire", "fr"),
    ("Liste la centrale nucléaire.", "FILTER_BY_CLASS", "CentraleNucleaire", "fr"),
    ("Quels sont les moyens de stockage électrique ?", "FILTER_BY_CLASS", "StockageElectrique", "fr"),
    ("Combien de sources de production existe-t-il ?", "COUNT_INDIVIDUALS", "SourceProduction", "fr"),
    ("Combien de centrales nucléaires existe-t-il ?", "COUNT_INDIVIDUALS", "CentraleNucleaire", "fr"),
    ("Quels types de stockage sont disponibles ?", "LIST_TYPES", "Stockage", "fr"),
    ("How many nuclear plants are there?", "COUNT_INDIVIDUALS", "CentraleNucleaire", "en"),
    ("List the nuclear plants.", "FILTER_BY_CLASS", "CentraleNucleaire", "en"),
    ("What types of storage are available?", "LIST_TYPES", "Stockage", "en"),
    ("List the storage facilities.", "LIST_INDIVIDUALS", "Stockage", "en"),
]

INJECTIONS = [
    "Combien de sources de production existe-t-il ? ; DROP ALL",
    "Liste les centrales nucléaires. INSERT DATA { <http://example.org/a> <http://example.org/p> 1 }",
    "SELECT * WHERE { ?s ?p ?o }",
    "Donne-moi les détails de CentraleTunis ; DROP ALL",
    "Liste les centrales nucléaires. } CLEAR ALL",
]


class Boom:
    def select(self, query: str) -> dict:
        raise AssertionError(query)


class FakeSparql:
    def __init__(self, bindings: list | None = None) -> None:
        self.bindings = bindings or []
        self.queries: list[str] = []

    def select(self, query: str) -> dict:
        self.queries.append(query)
        return {"results": {"bindings": self.bindings}}


def ask(question: str, bindings: list | None = None, *, boom: bool = False):
    service = Boom() if boom else FakeSparql(bindings)
    answer = answer_question(question, service=service)
    queries = [] if boom else service.queries
    return answer, queries


@pytest.mark.parametrize(("question", "intent", "class_name", "language"), EXAMPLES)
def test_supported_questions_generate_selects(question, intent, class_name, language):
    bindings = [{"count": {"value": "0"}}] if intent == "COUNT_INDIVIDUALS" else None
    answer, queries = ask(question, bindings)
    assert answer.intent == intent
    assert answer.language == language
    assert answer.clarification == ""
    assert answer.error == ""
    assert queries == [answer.sparql]
    validate_select(answer.sparql)
    SparqlService._require_select(None, answer.sparql)
    assert f"<{class_iri(class_name)}>" in answer.sparql
    assert "INSERT" not in answer.sparql.upper()
    assert "DELETE" not in answer.sparql.upper()
    assert question.split()[0] not in answer.sparql
    if intent == "COUNT_INDIVIDUALS":
        assert "COUNT" in answer.sparql
        assert "LIMIT 1" in answer.sparql
    else:
        assert "LIMIT 100" in answer.sparql
    if intent == "LIST_TYPES":
        assert "?class" in answer.sparql
    else:
        assert "?individual" in answer.sparql


def test_production_query_includes_nuclear_subclass():
    answer, _queries = ask("Quelles sources de production existent ?")
    module = get_module("SourceProduction")
    assert len(module.subtree_iris("SourceProduction")) == 16
    for iri in module.subtree_iris("SourceProduction"):
        assert f"<{iri}>" in answer.sparql
    assert f"<{class_iri('CentraleNucleaire')}>" in answer.sparql
    assert f"<{class_iri('VolantInertie')}>" not in answer.sparql


def test_electrical_storage_keeps_its_subtree():
    answer, _queries = ask("Quels sont les moyens de stockage électrique ?")
    for name in ("StockageElectrique", "BobineSupraconductrice", "Supercondensateur"):
        assert f"<{class_iri(name)}>" in answer.sparql
    assert f"<{class_iri('BatterieLFP')}>" not in answer.sparql
    assert f"<{class_iri('Stockage')}>" not in answer.sparql


def test_non_renewable_does_not_include_renewable_classes():
    answer, _queries = ask("Liste les énergies non renouvelables.")
    assert answer.intent == "FILTER_BY_CLASS"
    assert f"<{class_iri('EnergieNonRenouvelable')}>" in answer.sparql
    assert f"<{class_iri('CentraleGaz')}>" in answer.sparql
    assert f"<{class_iri('EnergieRenouvelable')}>" not in answer.sparql
    assert f"<{class_iri('PanneauPhotovoltaique')}>" not in answer.sparql


def test_offshore_is_more_specific_than_wind():
    answer, _queries = ask("Liste les éoliennes offshore.")
    assert answer.intent == "FILTER_BY_CLASS"
    assert f"<{class_iri('EolienneOffshore')}>" in answer.sparql
    assert f"<{class_iri('Eolien')}>" not in answer.sparql
    assert f"<{class_iri('EolienneTerrestre')}>" not in answer.sparql


def test_details_use_the_exact_individual_iri():
    bindings = [
        {
            "individual": {"type": "uri", "value": individual_iri("CentraleTunis")},
            "type": {"type": "uri", "value": class_iri("SourceProduction")},
        },
        {
            "individual": {"type": "uri", "value": individual_iri("CentraleTunis")},
            "type": {"type": "uri", "value": class_iri("CentraleNucleaire")},
        },
    ]
    answer, queries = ask("Donne-moi les détails de CentraleTunis.", bindings)
    assert answer.intent == "GET_DETAILS"
    assert answer.language == "fr"
    assert queries == [answer.sparql]
    validate_select(answer.sparql)
    assert answer.sparql.count(f"<{individual_iri('CentraleTunis')}>") == 1
    assert "Donne-moi" not in answer.sparql
    assert len(answer.rows) == 1
    assert answer.rows[0].title == "CentraleTunis"
    assert answer.rows[0].subtitle == "Centrale Nucleaire"
    assert answer.rows[0].href == "/sources/i/CentraleTunis/"


def test_details_accept_an_ontology_iri():
    iri = individual_iri("CentraleTunis")
    answer, queries = ask(f"Donne-moi les détails de {iri}")
    assert answer.intent == "GET_DETAILS"
    assert answer.sparql.count(f"<{iri}>") == 1
    assert queries == [answer.sparql]
    validate_select(answer.sparql)


def test_foreign_iri_is_not_executed():
    answer, queries = ask("Donne-moi les détails de http://example.org/CentraleTunis", boom=True)
    assert answer.clarification
    assert answer.sparql == ""
    assert queries == []
    answer, _queries = ask("Donne-moi les détails de CentraleTunis.")
    assert answer.intent == "GET_DETAILS"
    assert answer.rows == ()
    assert answer.empty_message
    assert answer.error == ""


def test_count_and_type_results():
    counted, _queries = ask(
        "Combien de centrales nucléaires existe-t-il ?",
        [{"count": {"type": "literal", "value": "0"}}],
    )
    assert counted.count == 0
    assert counted.empty_message == ""

    module = get_module("Stockage")
    listed, _queries = ask(
        "Quels types de stockage sont disponibles ?",
        [{"class": {"type": "uri", "value": item.iri}} for item in module.classes],
    )
    assert listed.intent == "LIST_TYPES"
    assert len(listed.rows) == 12
    assert listed.rows[0].title == "Stockage"
    assert listed.rows[0].href.startswith("/stockages/?rdf_type=Stockage")


def test_two_classes_are_not_guessed():
    answer, queries = ask(
        "Liste les centrales nucléaires et les barrages hydroélectriques.",
        boom=True,
    )
    assert answer.clarification
    assert answer.sparql == ""
    assert queries == []


def test_class_name_is_not_treated_as_an_individual():
    answer, queries = ask("Donne-moi les détails de CentraleNucleaire.", boom=True)
    assert "classe" in answer.clarification.lower()
    assert queries == []


@pytest.mark.parametrize("question", INJECTIONS)
def test_injection_never_reaches_fuseki(question):
    answer, queries = ask(question, boom=True)
    assert answer.clarification
    assert answer.sparql == ""
    assert queries == []


def test_validator_rejects_unsafe_queries():
    with pytest.raises(QueryRejected):
        validate_select("DROP ALL")
    with pytest.raises(QueryRejected):
        validate_select("INSERT DATA { <http://example.org/a> <http://example.org/p> <http://example.org/b> }")
    with pytest.raises(QueryRejected):
        validate_select("SELECT ?s WHERE { ?s ?p ?o } LIMIT 1")
    service_query = (
        "SELECT ?s WHERE { "
        "SERVICE <http://www.semanticweb.org/sanal/ontologies/2026/9/untitled-ontology-9#SourceProduction> "
        "{ ?s ?p ?o } } LIMIT 1"
    )
    with pytest.raises(QueryRejected):
        validate_select(service_query)


def test_every_supported_class_has_an_alias():
    covered = {alias.local_name for alias in alias_index()}
    for module in list_modules():
        for item in module.classes:
            assert item.local_name in covered


def test_normalization_and_crud_name_hook():
    assert normalize("Éoliennes") == "eoliennes"
    assert normalized_question("volant d'inertie") == "volant inertie"
    assert normalized_question("centrales nucléaires") == normalized_question("centrales nucleaires")
    assert prepare_individual_name("  Éolienne   Nord ") == "Éolienne Nord"


def test_question_form_collapses_whitespace():
    form = QuestionForm({"q": "  Quelles sources de production existent ?  "})
    assert form.is_valid()
    assert form.cleaned_data["q"] == "Quelles sources de production existent ?"


def test_sample_questions_are_supported():
    expected = {question for question, *_rest in EXAMPLES}
    expected.add("Donne-moi les détails de CentraleTunis.")
    for sample in SAMPLE_QUESTIONS:
        assert sample in expected


@pytest.mark.django_db
def test_routes_stay_available():
    assert reverse("home") == "/"
    assert reverse("questions") == "/questions/"
    assert reverse("source_production:list") == "/sources/"
    assert reverse("stockage:list") == "/stockages/"


@pytest.mark.django_db
def test_question_page_lists_samples_without_a_sparql_field(client):
    response = client.get("/questions/")
    body = response.content.decode()
    assert response.status_code == 200
    assert "Quelles sources de production existent ?" in body
    assert "Generated SPARQL" not in body
    assert 'name="q"' in body
    assert 'name="sparql"' not in body


@pytest.mark.django_db
def test_question_page_escapes_generated_sparql(client, monkeypatch):
    answer = Answer(
        question="Liste les centrales nucléaires.",
        language="fr",
        intent="FILTER_BY_CLASS",
        sparql=(
            "SELECT ?individual WHERE { "
            "<http://www.semanticweb.org/sanal/ontologies/2026/9/untitled-ontology-9#CentraleNucleaire> "
            "?p ?o } LIMIT 1\n"
        ),
        explanation="Individus.",
    )
    monkeypatch.setattr("web_sem.nlp.views.answer_question", lambda question: answer)
    response = client.get("/questions/", {"q": "Liste les centrales nucléaires."})
    body = response.content.decode()
    assert response.status_code == 200
    assert "Generated SPARQL" in body
    assert "FILTER_BY_CLASS" in body
    assert "&lt;http://www.semanticweb.org" in body
    assert "<http://www.semanticweb.org" not in body


@pytest.mark.django_db
def test_question_page_runs_the_pipeline(client, monkeypatch):
    def fake_select(self, query: str) -> dict:
        fake_select.queries.append(query)
        return {"results": {"bindings": [{"count": {"value": "1"}}]}}

    fake_select.queries = []
    monkeypatch.setattr("web_sem.nlp.service.SparqlService.select", fake_select)
    response = client.get("/questions/", {"q": "Combien de centrales nucléaires existe-t-il ?"})
    body = response.content.decode()
    assert response.status_code == 200
    assert "COUNT_INDIVIDUALS" in body
    assert fake_select.queries
    validate_select(fake_select.queries[0])
    assert f"<{class_iri('CentraleNucleaire')}>" in fake_select.queries[0]


@pytest.mark.django_db
def test_store_error_is_visible(client, monkeypatch):
    answer = Answer(
        question="x",
        error="The RDF store could not run this query.",
        http_status=503,
    )
    monkeypatch.setattr("web_sem.nlp.views.answer_question", lambda question: answer)
    response = client.get("/questions/", {"q": "x"})
    assert response.status_code == 503
    assert "RDF store" in response.content.decode()


@pytest.mark.django_db
def test_blank_question_stays_on_the_form(client):
    response = client.get("/questions/", {"q": "   "})
    assert response.status_code == 200
    assert b"This field is required" in response.content


@pytest.mark.django_db
def test_home_links_to_questions(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"/questions/" in response.content
