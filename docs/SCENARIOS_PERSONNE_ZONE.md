# Test scenarios: Personne and Zone

Prerequisite: Fuseki is running and `data/ontology/ENERGIE.rdf` is loaded into the `energy` dataset.

## A. Zone lifecycle
1. `/zones/` → **Nouvel individu** → class *Ville*, name `ville_gabes`, Nom de la zone `Gabès`, Région `Sud-Est` → Enregistrer.
   Expected: detail page lists `nomZone` and `region`.
2. Create `site_solaire_gabes`, class *Site Solaire*, Ville de rattachement `ville_gabes`, Puissance `35`.
   Expected: saved; the detail page of `ville_gabes` shows `appartientAVille` under "Liens entrants".
3. Create a *Ville* with a Puissance value. Expected: rejected ("ne s’applique pas à la classe").
4. Try the name `Ville`. Expected: rejected (reserved ontology name).
5. Modifier `site_solaire_gabes` → Puissance `40` → Enregistrer. Expected: the detail page shows 40.
6. Supprimer `site_solaire_gabes`. Expected: redirected to the list; it is gone.

## B. Personne lifecycle
1. `/personnes/` → **Nouvel individu** → *Technicien Ligne*, name `tech_sami`, Nom complet `Sami`, Matricule `TLG-002`, Affecté à `ville_gabes`.
   Expected: detail shows the properties; `ville_gabes` shows `estAffecteA` as an incoming link.
2. Create a *Client Abonné* with Ville de résidence `ville_gabes`; try the same on an *Opérateur*. Expected: only the client is accepted.
3. Filter the list by class *Technicien*. Expected: `tech_sami` appears (subclasses included), engineers and operators do not.
4. Enter an invalid e-mail. Expected: validation error.

## C. Scenarios page (`/scenarios/`)
| Scenario | Check |
|---|---|
| Qui travaille où ? | `tech_sami` appears with zone `ville_gabes`. |
| Techniciens disponibles dans une zone | Pick `ville_gabes`: `tech_sami`, speciality `TechnicienLigne`. |
| Personnel sans affectation | `Technicien_Walid` (sample data) is listed; `tech_sami` is not. |
| Effectif par zone | `ville_gabes` and `Ville_Sfax` have counts. |
| Sites d’une ville | Pick `Ville_Tozeur`: `SiteSolaire_Tozeur`, 50 MW. |
| Puissance installée par type de site | Solaire 50, Éolien 120 (sample data). |
| Clients abonnés par ville | Counts clients with `residentDans`. |

## D. Cross-checks
- `/graph/` with class *Zone* or *Personne* shows the `estAffecteA` and `appartientAVille` edges.
- `/questions/` → "Quels sont les techniciens ?" lists the technician individuals.
- `/creation/` (assisted creation): `nomZone=Gafsa` is accepted as a property.
- Automated: `python -m pytest tests/test_personne_zone.py -q`
