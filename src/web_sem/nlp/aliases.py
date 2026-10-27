"""Map question words to ontology classes using spaCy lemmas.

Every class name is an alias automatically. SUBJECTS only adds synonyms.
Write them in the singular: lemmatization handles plurals and verb forms.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

from web_sem.nlp.catalog import all_class_names, known_names
from web_sem.nlp.normalize import normalized_question
from web_sem.ontology import OntologyError

# language -> class -> synonyms
SUBJECTS: dict[str, dict[str, list[str]]] = {
    "fr": {
        "Consommateur": ["consommation", "consommer", "énergie consommée"],
        "SourceProduction": ["production", "produire", "producteur", "énergie produite", "source de production"],
        "Hydraulique": ["hydroélectrique", "hydro-électrique"],
        "BarrageHydroelectrique": ["barrage hydroélectrique"],
        "CentraleAuFil": ["centrale au fil de l'eau", "au fil de l'eau"],
        "Solaire": ["solaire"],
        "CentraleSolaireThermique": ["centrale solaire thermique", "solaire thermique"],
        "PanneauPhotovoltaique": ["panneau photovoltaïque", "photovoltaïque"],
        "Stockage": ["stockage", "moyen de stockage"],
        "StockageElectrique": ["stockage électrique"],
        "StockageElectrochimique": ["stockage électrochimique", "électrochimique"],
        "BatterieLithiumIon": ["batterie lithium-ion", "lithium-ion"],
        "BatteriePlombAcide": ["batterie plomb-acide", "plomb-acide"],
        "StationPompage": ["station de pompage"],
        "VolantInertie": ["volant d'inertie"],
        "Poste": ["poste"],
        "PosteSource": ["poste source"],
        "PosteTransformation": ["poste de transformation"],
        "LigneTransport": ["ligne de transport", "ligne électrique", "ligne électrique de transport"],
        "Infrastructure": ["infrastructure"],
        # Personne
        "Personne": ["personnel", "employé"],
        "ClientAbonne": ["client", "abonné", "client abonné"],
        "TechnicienMaintenance": ["technicien de maintenance"],
        "TechnicienLigne": ["technicien de ligne"],
        "TechnicienPoste": ["technicien de poste"],
        "TechnicienExploitation": ["technicien d'exploitation", "technicien de l'exploitation"],
        # Zone
        "SiteInstallation": ["site", "site d'installation"],
        "SiteProduction": ["site de production"],
        "SiteStockage": ["site de stockage"],
        "SiteSolaire": ["site solaire", "parc solaire"],
        "SiteEolien": ["site éolien", "parc éolien"],
        # Infrastructure et Zone (équipe)
        "LigneBasseTension": ["ligne basse tension"],
        "LigneBasseTensionAerienne": ["ligne basse tension aérienne"],
        "LigneBasseTensionSouterraine": ["ligne basse tension souterraine"],
        "LigneHauteTension": ["ligne haute tension"],
        "LigneHauteTensionAerienne": ["ligne haute tension aérienne"],
        "LigneHauteTensionSouterraine": ["ligne haute tension souterraine"],
        "LigneMoyenneTension": ["ligne moyenne tension"],
        "LigneMoyenneTensionAerienne": ["ligne moyenne tension aérienne"],
        "LigneMoyenneTensionSouterraine": ["ligne moyenne tension souterraine"],
        "Ville": ["ville"],
        # Evenement
        "Evenement": ["événement", "evenement", "incident"],
        "AlerteSurcharge": ["alerte de surcharge", "alerte surcharge"],
        "Maintenance": ["maintenance", "opération de maintenance"],
        "MaintenanceCorrective": ["maintenance corrective", "réparation"],
        "MaintenancePreventive": ["maintenance préventive", "entretien préventif"],
        "Panne": ["panne"],
        "PanneElectrique": ["panne électrique", "défaut électrique"],
        "CoupureAlimentation": ["coupure d'alimentation", "coupure de courant"],
        "CourtCircuit": ["court-circuit", "court circuit"],
        "PanneMecanique": ["panne mécanique", "défaut mécanique"],
        # CapteurDispositif
        "CapteurDispositif": ["capteur", "dispositif", "capteur ou dispositif"],
        "CapteurProduction": ["capteur de production"],
        "CapteurProductionRenouvelable": ["capteur de production renouvelable", "capteur renouvelable"],
        "CapteurEolien": ["capteur éolien", "anémomètre"],
        "CapteurPhotovoltaique": ["capteur photovoltaïque"],
        "CapteurProductionThermique": ["capteur de production thermique", "capteur thermique"],
        "CompteurIntelligent": ["compteur intelligent", "smart meter"],
    },
    "en": {
        "Consommateur": ["consumer"],
        "SourceProduction": ["production source", "producer"],
        "Hydraulique": ["hydropower"],
        "BarrageHydroelectrique": ["hydroelectric dam"],
        "CentraleAuFil": ["run-of-river plant"],
        "CentraleNucleaire": ["nuclear plant", "nuclear power plant"],
        "Solaire": ["solar", "solar power"],
        "CentraleSolaireThermique": ["solar thermal plant"],
        "PanneauPhotovoltaique": ["photovoltaic panel"],
        "Stockage": ["storage", "storage facility"],
        "StockageElectrique": ["electrical storage"],
        "BatterieLithiumIon": ["lithium-ion battery"],
        "StationPompage": ["pumped storage"],
        "VolantInertie": ["flywheel"],
        "Poste": ["substation"],
        "PosteSource": ["source substation"],
        "PosteTransformation": ["transformation substation"],
        "LigneTransport": ["transport line"],
        "Infrastructure": ["infrastructure"],
        # Evenement
        "Evenement": ["event", "incident"],
        "AlerteSurcharge": ["overload alert"],
        "Maintenance": ["maintenance operation"],
        "MaintenanceCorrective": ["corrective maintenance"],
        "MaintenancePreventive": ["preventive maintenance"],
        "Panne": ["outage", "breakdown"],
        "PanneElectrique": ["electrical outage", "electrical failure"],
        "CoupureAlimentation": ["power cut", "power outage"],
        "CourtCircuit": ["short circuit"],
        "PanneMecanique": ["mechanical failure"],
        # CapteurDispositif
        "CapteurDispositif": ["sensor", "device"],
        "CapteurProduction": ["production sensor"],
        "CapteurProductionRenouvelable": ["renewable production sensor"],
        "CapteurEolien": ["wind sensor"],
        "CapteurPhotovoltaique": ["photovoltaic sensor"],
        "CapteurProductionThermique": ["thermal production sensor"],
        "CompteurIntelligent": ["smart meter", "intelligent meter"],
    },
}

_CUES: dict[str, dict[str, tuple[str, ...]]] = {
    "fr": {
        "count": ("combien", "nombre de", "combien y a t il", "combien de", "quel est le nombre de"),
        "types": ("quels types", "quel type", "quelles classes", "quelle classe",
                  "types de", "classes de", "catégories de", "catégorie de"),
        "details": ("détails de", "détails du", "détails des", "détail de", "détail du",
                    "fiche de", "informations sur", "information sur"),
        "list": ("liste", "lister", "quelles", "quels", "quelle", "quel", "existe", "existent",
                 "montre", "montre moi", "afficher", "affiche", "affiche moi", "donne",
                 "donne moi", "quels sont", "quelles sont", "quels sont les", "quelles sont les"),
    },
    "en": {
        "count": ("how many", "number of", "how many are there", "how many does"),
        "types": ("what types", "which types", "types of", "classes of", "what classes", "which classes"),
        "details": ("details of", "details for", "detail of", "information about"),
        "list": ("list", "which", "what", "show", "show me", "tell me", "give me",
                 "what are", "which are"),
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


def _split_camel(name: str) -> str:
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", name)


@lru_cache(maxsize=1)
def alias_index() -> tuple[Alias, ...]:
    known = known_names()
    found: dict[str, Alias] = {}

    def add(phrase: str, local_name: str, language: str) -> None:
        key = normalized_question(phrase)          # lemmatized, like the question
        if not key:
            raise OntologyError(f"Alias has no searchable text: {phrase}")
        current = found.get(key)
        if current and current.local_name != local_name:
            raise OntologyError(
                f"Alias {phrase!r} matches both {current.local_name} and {local_name}."
            )
        found.setdefault(key, Alias(key, local_name, language))

    for language, classes in SUBJECTS.items():
        for local_name, words in classes.items():
            if local_name not in known:
                raise OntologyError(f"Alias target is not a supported class: {local_name}")
            for word in words:
                add(word, local_name, language)

    for local_name in all_class_names():            # every class, automatically
        add(_split_camel(local_name), local_name, "fr")

    return tuple(sorted(found.values(), key=lambda a: (-len(a.phrase), a.phrase)))


@lru_cache(maxsize=1)
def cue_index() -> tuple[Cue, ...]:
    cues = []
    for language, groups in _CUES.items():
        for kind, phrases in groups.items():
            for phrase in phrases:
                key = normalized_question(phrase)
                if key:
                    cues.append(Cue(key, kind, language))
    return tuple(cues)