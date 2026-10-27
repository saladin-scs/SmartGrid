"""Read-only SPARQL scenarios that link people and zones.

Each scenario answers a business question. Class sets come from ENERGIE.rdf
(subtree IRIs), so the queries do not depend on the hierarchy being loaded in Fuseki.
"""

from __future__ import annotations

from dataclasses import dataclass

from web_sem.ontology import ONTOLOGY_NS, get_module, individual_iri
from web_sem.repository import IndividualRepository, _iris
from web_sem.sparql import SparqlService


@dataclass(frozen=True, slots=True)
class Scenario:
    key: str
    title: str
    actor: str
    description: str
    columns: tuple[tuple[str, str], ...]
    param: str = ""  # a Zone individual is requested when set
    param_label: str = ""


def _p(name: str) -> str:
    return f"<{ONTOLOGY_NS}{name}>"


def _classes(root: str, *subroots: str | None) -> str:
    module = get_module(root)
    names: list[str] = []
    for sub in subroots or (None,):
        names += module.subtree_iris(sub)
    return _iris(names)


SCENARIOS: tuple[Scenario, ...] = (
    Scenario(
        "affectations",
        "Qui travaille où ?",
        "Responsable d’exploitation",
        "Toutes les personnes avec leur classe et la zone où elles sont affectées.",
        (("nom", "Nom"), ("personne", "Individu"), ("classe", "Classe"), ("zone", "Zone")),
    ),
    Scenario(
        "techniciens_zone",
        "Techniciens disponibles dans une zone",
        "Chef de maintenance",
        "Techniciens (maintenance, ligne, poste, exploitation) affectés à la zone choisie.",
        (("nom", "Nom"), ("personne", "Individu"), ("classe", "Spécialité")),
        param="Zone",
        param_label="Zone",
    ),
    Scenario(
        "sans_affectation",
        "Personnel sans affectation",
        "Ressources humaines",
        "Ingénieurs, opérateurs et techniciens qui n’ont aucune zone d’affectation : à planifier.",
        (("personne", "Individu"), ("classe", "Classe")),
    ),
    Scenario(
        "effectif_par_zone",
        "Effectif par zone",
        "Direction",
        "Nombre de personnes affectées à chaque zone, de la plus chargée à la moins chargée.",
        (("zone", "Zone"), ("effectif", "Personnes")),
    ),
    Scenario(
        "sites_ville",
        "Sites d’une ville",
        "Planificateur réseau",
        "Sites de production et de stockage rattachés à la ville choisie, avec leur puissance.",
        (("site", "Site"), ("classe", "Type"), ("puissance", "Puissance (MW)")),
        param="Ville",
        param_label="Ville",
    ),
    Scenario(
        "puissance_par_type",
        "Puissance installée par type de site",
        "Direction",
        "Nombre de sites et puissance installée totale (MW) par type de site de production.",
        (("classe", "Type de site"), ("sites", "Sites"), ("total", "Total MW")),
    ),
    Scenario(
        "clients_ville",
        "Clients abonnés par ville",
        "Service commercial",
        "Nombre de clients abonnés résidant dans chaque ville.",
        (("ville", "Ville"), ("clients", "Clients")),
    ),
)
BY_KEY = {item.key: item for item in SCENARIOS}


def build_query(key: str, value: str = "") -> str:
    if key == "affectations":
        return f"""
        SELECT ?nom ?personne ?classe ?zone WHERE {{
          VALUES ?t {{ {_classes('Personne')} }}
          ?p a ?t ; {_p('estAffecteA')} ?z .
          OPTIONAL {{ ?p {_p('nomPersonne')} ?n }}
          BIND(COALESCE(?n, STRAFTER(STR(?p), "#")) AS ?nom)
          BIND(STRAFTER(STR(?p), "#") AS ?personne)
          BIND(STRAFTER(STR(?t), "#") AS ?classe)
          BIND(STRAFTER(STR(?z), "#") AS ?zone)
        }} ORDER BY ?zone ?classe ?personne"""
    if key == "techniciens_zone":
        return f"""
        SELECT ?nom ?personne ?classe WHERE {{
          VALUES ?t {{ {_classes('Personne', 'Technicien')} }}
          ?p a ?t ; {_p('estAffecteA')} <{individual_iri(value)}> .
          OPTIONAL {{ ?p {_p('nomPersonne')} ?n }}
          BIND(COALESCE(?n, STRAFTER(STR(?p), "#")) AS ?nom)
          BIND(STRAFTER(STR(?p), "#") AS ?personne)
          BIND(STRAFTER(STR(?t), "#") AS ?classe)
        }} ORDER BY ?classe ?personne"""
    if key == "sans_affectation":
        staff = _classes("Personne", "Ingenieur", "Operateur", "Technicien")
        return f"""
        SELECT ?personne ?classe WHERE {{
          VALUES ?t {{ {staff} }}
          ?p a ?t .
          FILTER NOT EXISTS {{ ?p {_p('estAffecteA')} ?z }}
          BIND(STRAFTER(STR(?p), "#") AS ?personne)
          BIND(STRAFTER(STR(?t), "#") AS ?classe)
        }} ORDER BY ?classe ?personne"""
    if key == "effectif_par_zone":
        return f"""
        SELECT ?zone (COUNT(DISTINCT ?p) AS ?effectif) WHERE {{
          ?p {_p('estAffecteA')} ?z .
          BIND(STRAFTER(STR(?z), "#") AS ?zone)
        }} GROUP BY ?zone ORDER BY DESC(?effectif) ?zone"""
    if key == "sites_ville":
        return f"""
        SELECT ?site ?classe ?puissance WHERE {{
          VALUES ?t {{ {_classes('Zone', 'SiteInstallation')} }}
          ?s a ?t ; {_p('appartientAVille')} <{individual_iri(value)}> .
          OPTIONAL {{ ?s {_p('puissanceInstalleeMW')} ?pw }}
          BIND(STRAFTER(STR(?s), "#") AS ?site)
          BIND(STRAFTER(STR(?t), "#") AS ?classe)
          BIND(COALESCE(STR(?pw), "—") AS ?puissance)
        }} ORDER BY ?classe ?site"""
    if key == "puissance_par_type":
        return f"""
        SELECT ?classe (COUNT(DISTINCT ?s) AS ?sites) (SUM(?pw) AS ?total) WHERE {{
          VALUES ?t {{ {_classes('Zone', 'SiteProduction')} }}
          ?s a ?t ; {_p('puissanceInstalleeMW')} ?pw .
          BIND(STRAFTER(STR(?t), "#") AS ?classe)
        }} GROUP BY ?classe ORDER BY DESC(?total)"""
    if key == "clients_ville":
        return f"""
        SELECT ?ville (COUNT(DISTINCT ?p) AS ?clients) WHERE {{
          ?p {_p('residentDans')} ?v .
          BIND(STRAFTER(STR(?v), "#") AS ?ville)
        }} GROUP BY ?ville ORDER BY DESC(?clients) ?ville"""
    raise KeyError(key)


def run(scenario: Scenario, value: str = "", service: SparqlService | None = None):
    query = build_query(scenario.key, value)
    payload = (service or SparqlService()).select(query)
    rows = [
        [(binding.get(col) or {}).get("value", "") for col, _ in scenario.columns]
        for binding in payload["results"]["bindings"]
    ]
    return query.strip(), rows


def param_choices(scenario: Scenario) -> list[str]:
    """Existing individuals the scenario can be run on (a city or any zone)."""
    module = get_module("Zone")
    class_name = "" if scenario.param == "Zone" else scenario.param
    return [item.local_name for item in IndividualRepository().list_individuals(module, class_name=class_name)]
