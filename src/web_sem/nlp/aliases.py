"""Controlled phrases for the two supported languages.

Add a language by extending ``_ALIASES`` and ``_CUES`` and the message tables
in :mod:`web_sem.nlp.interpret`. Matching stays exact after normalization, so
plurals and spelling variants are listed here instead of being guessed.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from web_sem.nlp.catalog import all_class_names, known_names
from web_sem.nlp.normalize import normalized_question
from web_sem.ontology import OntologyError

# (language, phrase, ontology class local name)
_ALIASES: tuple[tuple[str, str, str], ...] = (
    ("fr", "sources de production", "SourceProduction"),
    ("fr", "source de production", "SourceProduction"),
    ("fr", "sources production", "SourceProduction"),
    ("fr", "source production", "SourceProduction"),
    ("en", "production sources", "SourceProduction"),
    ("en", "production source", "SourceProduction"),
    ("en", "power sources", "SourceProduction"),
    ("en", "power source", "SourceProduction"),
    ("fr", "énergie non renouvelable", "EnergieNonRenouvelable"),
    ("fr", "énergies non renouvelables", "EnergieNonRenouvelable"),
    ("fr", "non renouvelable", "EnergieNonRenouvelable"),
    ("fr", "non renouvelables", "EnergieNonRenouvelable"),
    ("en", "non-renewable energy", "EnergieNonRenouvelable"),
    ("en", "nonrenewable energy", "EnergieNonRenouvelable"),
    ("fr", "centrale à charbon", "CentraleCharbon"),
    ("fr", "centrales à charbon", "CentraleCharbon"),
    ("fr", "centrale charbon", "CentraleCharbon"),
    ("en", "coal plant", "CentraleCharbon"),
    ("en", "coal plants", "CentraleCharbon"),
    ("fr", "centrale à gaz", "CentraleGaz"),
    ("fr", "centrales à gaz", "CentraleGaz"),
    ("fr", "centrale gaz", "CentraleGaz"),
    ("en", "gas plant", "CentraleGaz"),
    ("en", "gas plants", "CentraleGaz"),
    ("fr", "centrale nucléaire", "CentraleNucleaire"),
    ("fr", "centrales nucléaires", "CentraleNucleaire"),
    ("fr", "nucléaire", "CentraleNucleaire"),
    ("fr", "nucléaires", "CentraleNucleaire"),
    ("en", "nuclear plant", "CentraleNucleaire"),
    ("en", "nuclear plants", "CentraleNucleaire"),
    ("en", "nuclear power plant", "CentraleNucleaire"),
    ("en", "nuclear power plants", "CentraleNucleaire"),
    ("fr", "énergie renouvelable", "EnergieRenouvelable"),
    ("fr", "énergies renouvelables", "EnergieRenouvelable"),
    ("fr", "renouvelable", "EnergieRenouvelable"),
    ("fr", "renouvelables", "EnergieRenouvelable"),
    ("en", "renewable energy", "EnergieRenouvelable"),
    ("fr", "biomasse", "Biomasse"),
    ("en", "biomass", "Biomasse"),
    ("fr", "éolien", "Eolien"),
    ("fr", "éolienne", "Eolien"),
    ("fr", "éoliennes", "Eolien"),
    ("fr", "énergie éolienne", "Eolien"),
    ("en", "wind power", "Eolien"),
    ("en", "wind turbine", "Eolien"),
    ("en", "wind turbines", "Eolien"),
    ("fr", "éolienne offshore", "EolienneOffshore"),
    ("fr", "éoliennes offshore", "EolienneOffshore"),
    ("fr", "éolienne off-shore", "EolienneOffshore"),
    ("fr", "éoliennes off-shore", "EolienneOffshore"),
    ("en", "offshore wind turbine", "EolienneOffshore"),
    ("en", "offshore wind turbines", "EolienneOffshore"),
    ("fr", "éolienne terrestre", "EolienneTerrestre"),
    ("fr", "éoliennes terrestres", "EolienneTerrestre"),
    ("en", "onshore wind turbine", "EolienneTerrestre"),
    ("en", "onshore wind turbines", "EolienneTerrestre"),
    ("fr", "hydraulique", "Hydraulique"),
    ("fr", "hydroélectrique", "Hydraulique"),
    ("fr", "hydro-électrique", "Hydraulique"),
    ("en", "hydropower", "Hydraulique"),
    ("fr", "barrage hydroélectrique", "BarrageHydroelectrique"),
    ("fr", "barrages hydroélectriques", "BarrageHydroelectrique"),
    ("en", "hydroelectric dam", "BarrageHydroelectrique"),
    ("en", "hydroelectric dams", "BarrageHydroelectrique"),
    ("fr", "centrale au fil de l'eau", "CentraleAuFil"),
    ("fr", "centrales au fil de l'eau", "CentraleAuFil"),
    ("fr", "au fil de l'eau", "CentraleAuFil"),
    ("en", "run-of-river plant", "CentraleAuFil"),
    ("en", "run of river plant", "CentraleAuFil"),
    ("fr", "solaire", "Solaire"),
    ("en", "solar power", "Solaire"),
    ("en", "solar", "Solaire"),
    ("fr", "centrale solaire thermique", "CentraleSolaireThermique"),
    ("fr", "centrales solaires thermiques", "CentraleSolaireThermique"),
    ("fr", "solaire thermique", "CentraleSolaireThermique"),
    ("en", "solar thermal plant", "CentraleSolaireThermique"),
    ("en", "solar thermal plants", "CentraleSolaireThermique"),
    ("fr", "panneau photovoltaïque", "PanneauPhotovoltaique"),
    ("fr", "panneaux photovoltaïques", "PanneauPhotovoltaique"),
    ("fr", "photovoltaïque", "PanneauPhotovoltaique"),
    ("en", "photovoltaic panel", "PanneauPhotovoltaique"),
    ("en", "photovoltaic panels", "PanneauPhotovoltaique"),
    ("fr", "stockage", "Stockage"),
    ("fr", "stockages", "Stockage"),
    ("fr", "moyen de stockage", "Stockage"),
    ("fr", "moyens de stockage", "Stockage"),
    ("en", "storage facility", "Stockage"),
    ("en", "storage facilities", "Stockage"),
    ("en", "storage", "Stockage"),
    ("fr", "stockage électrique", "StockageElectrique"),
    ("fr", "stockages électriques", "StockageElectrique"),
    ("fr", "moyen de stockage électrique", "StockageElectrique"),
    ("fr", "moyens de stockage électrique", "StockageElectrique"),
    ("en", "electrical storage", "StockageElectrique"),
    ("en", "electric storage", "StockageElectrique"),
    ("fr", "bobine supraconductrice", "BobineSupraconductrice"),
    ("fr", "bobines supraconductrices", "BobineSupraconductrice"),
    ("en", "superconducting coil", "BobineSupraconductrice"),
    ("en", "superconducting coils", "BobineSupraconductrice"),
    ("fr", "supercondensateur", "Supercondensateur"),
    ("fr", "supercondensateurs", "Supercondensateur"),
    ("en", "supercapacitor", "Supercondensateur"),
    ("en", "supercapacitors", "Supercondensateur"),
    ("fr", "stockage électrochimique", "StockageElectrochimique"),
    ("fr", "stockages électrochimiques", "StockageElectrochimique"),
    ("fr", "électrochimique", "StockageElectrochimique"),
    ("en", "electrochemical storage", "StockageElectrochimique"),
    ("fr", "batterie lithium-ion", "BatterieLithiumIon"),
    ("fr", "batteries lithium-ion", "BatterieLithiumIon"),
    ("fr", "batterie lithium ion", "BatterieLithiumIon"),
    ("fr", "lithium-ion", "BatterieLithiumIon"),
    ("en", "lithium-ion battery", "BatterieLithiumIon"),
    ("en", "lithium-ion batteries", "BatterieLithiumIon"),
    ("en", "lithium ion battery", "BatterieLithiumIon"),
    ("fr", "batterie LFP", "BatterieLFP"),
    ("fr", "batteries LFP", "BatterieLFP"),
    ("fr", "batterie lithium fer phosphate", "BatterieLFP"),
    ("en", "LFP battery", "BatterieLFP"),
    ("en", "LFP batteries", "BatterieLFP"),
    ("fr", "batterie NMC", "BatterieNMC"),
    ("fr", "batteries NMC", "BatterieNMC"),
    ("en", "NMC battery", "BatterieNMC"),
    ("en", "NMC batteries", "BatterieNMC"),
    ("fr", "batterie plomb-acide", "BatteriePlombAcide"),
    ("fr", "batteries plomb-acide", "BatteriePlombAcide"),
    ("fr", "batterie plomb acide", "BatteriePlombAcide"),
    ("fr", "plomb-acide", "BatteriePlombAcide"),
    ("en", "lead-acid battery", "BatteriePlombAcide"),
    ("en", "lead-acid batteries", "BatteriePlombAcide"),
    ("en", "lead acid battery", "BatteriePlombAcide"),
    ("fr", "stockage mécanique", "StockageMecanique"),
    ("fr", "stockages mécaniques", "StockageMecanique"),
    ("en", "mechanical storage", "StockageMecanique"),
    ("fr", "station de pompage", "StationPompage"),
    ("fr", "stations de pompage", "StationPompage"),
    ("en", "pumped storage plant", "StationPompage"),
    ("en", "pumped storage plants", "StationPompage"),
    ("en", "pumped storage", "StationPompage"),
    ("fr", "volant d'inertie", "VolantInertie"),
    ("fr", "volants d'inertie", "VolantInertie"),
    ("en", "flywheel", "VolantInertie"),
    ("en", "flywheels", "VolantInertie"),
    ("fr", "consommateur", "Consommateur"),
    ("fr", "consommateurs", "Consommateur"),
    ("en", "consumer", "Consommateur"),
    ("en", "consumers", "Consommateur"),
    ("fr", "bâtiment industriel", "BatimentIndustriel"),
    ("en", "industrial building", "BatimentIndustriel"),
    ("fr", "bâtiment résidentiel", "BatimentResidentiel"),
    ("en", "residential building", "BatimentResidentiel"),
    ("fr", "immeuble", "Immeuble"),
    ("en", "apartment building", "Immeuble"),
    ("fr", "maison", "Maison"),
    ("en", "house", "Maison"),
    ("fr", "maison jumelée", "MaisonJumelee"),
    ("en", "semi-detached house", "MaisonJumelee"),
    ("fr", "villa individuelle", "VillaIndividuelle"),
    ("en", "detached villa", "VillaIndividuelle"),
    ("fr", "bâtiment tertiaire", "BatimentTertiaire"),
    ("en", "tertiary building", "BatimentTertiaire"),
    ("fr", "bureau", "Bureau"),
    ("en", "office", "Bureau"),
    ("fr", "commerce grande surface", "CommerceGrandeSurface"),
    ("en", "large retail store", "CommerceGrandeSurface"),
    ("fr", "hypermarché", "Hypermarche"),
    ("en", "hypermarket", "Hypermarche"),
    ("fr", "supermarché", "Supermarche"),
    ("en", "supermarket", "Supermarche"),
    ("fr", "véhicule électrique", "VehiculeElectrique"),
    ("en", "electric vehicle", "VehiculeElectrique"),
    ("fr", "contrat", "Contrat"),
    ("fr", "contrats", "Contrat"),
    ("en", "contract", "Contrat"),
    ("en", "contracts", "Contrat"),
    ("fr", "contrat abonnement", "ContratAbonnement"),
    ("en", "subscription contract", "ContratAbonnement"),
    ("fr", "abonnement professionnel", "AbonnementProfessionnel"),
    ("en", "professional subscription", "AbonnementProfessionnel"),
    ("fr", "abonnement commercial", "AbonnementCommercial"),
    ("en", "commercial subscription", "AbonnementCommercial"),
    ("fr", "abonnement industriel", "AbonnementIndustriel"),
    ("en", "industrial subscription", "AbonnementIndustriel"),
    ("fr", "abonnement résidentiel", "AbonnementResidentiel"),
    ("en", "residential subscription", "AbonnementResidentiel"),
    ("fr", "facture", "Facture"),
    ("en", "invoice", "Facture"),
)

_CUES: dict[str, dict[str, tuple[str, ...]]] = {
    "fr": {
        "count": ("combien", "nombre de"),
        "types": (
            "quels types",
            "quel type",
            "quelles classes",
            "quelle classe",
            "types de",
            "classes de",
            "catégories de",
            "catégorie de",
        ),
        "details": (
            "détails de",
            "détails du",
            "détails des",
            "détail de",
            "détail du",
            "fiche de",
            "informations sur",
            "information sur",
        ),
        "list": (
            "liste",
            "lister",
            "quelles",
            "quels",
            "quelle",
            "quel",
            "existe",
            "existent",
            "montre",
            "afficher",
            "quels sont",
            "quelles sont",
        ),
    },
    "en": {
        "count": ("how many", "number of"),
        "types": (
            "what types",
            "which types",
            "types of",
            "classes of",
            "what classes",
            "which classes",
        ),
        "details": ("details of", "details for", "detail of", "information about"),
        "list": ("list", "which", "what", "show"),
    },
}


@dataclass(frozen=True, slots=True)
class Alias:
    phrase: str
    local_name: str
    language: str


@dataclass(frozen=True, slots=True)
class Cue:
    phrase: str
    kind: str
    language: str


@lru_cache(maxsize=1)
def alias_index() -> tuple[Alias, ...]:
    known = known_names()
    found: dict[str, Alias] = {}
    for language, phrase, local_name in _ALIASES:
        if local_name not in known:
            raise OntologyError(f"Alias target is not a supported class: {local_name}")
        key = normalized_question(phrase)
        if not key:
            raise OntologyError(f"Alias has no searchable text: {phrase}")
        current = found.get(key)
        if current and current.local_name != local_name:
            raise OntologyError(
                f"Alias {phrase!r} matches both {current.local_name} and {local_name}."
            )
        if current is None:
            found[key] = Alias(key, local_name, language)
    for local_name in all_class_names():
        key = normalized_question(local_name)
        current = found.get(key)
        if current and current.local_name != local_name:
            raise OntologyError(
                f"Ontology class name {local_name!r} conflicts with alias for "
                f"{current.local_name}."
            )
        if current is None:
            found[key] = Alias(key, local_name, "fr")
    return tuple(sorted(found.values(), key=lambda item: (-len(item.phrase), item.phrase)))


@lru_cache(maxsize=1)
def cue_index() -> tuple[Cue, ...]:
    cues: list[Cue] = []
    for language, groups in _CUES.items():
        for kind, phrases in groups.items():
            for phrase in phrases:
                key = normalized_question(phrase)
                if key:
                    cues.append(Cue(key, kind, language))
    return tuple(cues)
