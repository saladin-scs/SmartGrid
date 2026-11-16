# SmartGrid

SmartGrid est une plateforme d'information énergétique fondée sur une ontologie. Elle associe une application web Django, l'ontologie RDF ENERGIE et Apache Jena Fuseki pour explorer les données du système énergétique à l'aide de tableaux de bord, d'un explorateur de graphe, d'une recherche sémantique et de questions en langage naturel.

## Une IA différente

L'IA de SmartGrid est **ancrée dans les données, explicable et spécialisée dans son domaine**. Elle ne demande pas à un modèle de langage génératif d'inventer une réponse : elle traduit la question de l'utilisateur en une requête contrôlée sur le graphe de connaissances ENERGIE, puis présente les données renvoyées par Fuseki.

Le pipeline de TALN (traitement automatique du langage naturel), principalement conçu pour le français, utilise le modèle spaCy `fr_core_news_sm` pour la tokenisation et la lemmatisation. Un mécanisme de repli plus léger est disponible si le modèle n'est pas installé. Les noms de classes de l'ontologie et des alias français et anglais sélectionnés relient les formulations courantes aux concepts et relations définis dans le schéma RDF.

### Étapes du traitement des questions

1. **Normalisation** : uniformiser les espaces, retirer les accents et la ponctuation pour faciliter la recherche, puis lemmatiser les tokens.
2. **Interprétation** : analyser les indices linguistiques et les termes du domaine afin d'identifier l'intention — par exemple, lister des individus, compter des instances, lister des types de classes, obtenir des détails ou interroger des données par zone et relation.
3. **Ancrage dans l'ontologie** : faire correspondre les classes, propriétés, zones et individus avec le catalogue de l'ontologie et, si nécessaire, avec le jeu de données Fuseki. Une question ambiguë ou non résolue peut déclencher une demande de clarification.
4. **Génération et validation** : construire une requête SPARQL `SELECT` à partir de modèles définis par l'ontologie et la valider. Le texte de la question n'est pas inséré dans la requête ; les requêtes générées pour le système de questions-réponses sont en lecture seule, limitées à l'ontologie et plafonnées en nombre de résultats.
5. **Exécution et présentation** : exécuter la requête au moyen du client Fuseki partagé, puis mettre en forme les résultats et fournir une explication en langage naturel.

Exemples de questions : *« Combien de centrales nucléaires existe-t-il ? »*, *« Quels techniciens travaillent à Sfax ? »* et *“How many nuclear plants are there?”*. Il s'agit d'analyse sémantique et de questions-réponses sur un graphe de connaissances, et non d'une conversation généraliste. Les réponses dépendent de l'ontologie et des données disponibles dans Fuseki.

Le processus distinct de création en langage naturel extrait les propriétés de l'ontologie à partir d'une description et affiche un aperçu RDF. L'écriture n'a lieu qu'après examen et confirmation explicite de cet aperçu par l'utilisateur.

## Fonctionnalités

- Espace de travail Django pour les classes de l'ontologie ENERGIE et les individus RDF.
- Vue d'ensemble et répartition des classes alimentées par Fuseki, ainsi qu'un explorateur de graphe RDF en lecture seule avec limites de résultats.
- Questions-réponses en langage naturel sur l'ontologie, principalement en français, avec prise en charge d'indices bilingues.
- Création d'individus RDF en langage naturel avec aperçu et confirmation.
- Pages Django générées côté serveur avec Tailwind CSS, icônes Lucide, Chart.js et Cytoscape.js.
- Interface d'administration Django personnalisée avec Django Unfold.

## Technologies

| Domaine | Technologies |
| --- | --- |
| Application web | Python 3.13+, Django 5.2, Django Cotton |
| TALN | spaCy, `fr_core_news_sm`, lemmatisation, alias d'ontologie et classification d'intentions |
| Données sémantiques | RDF, ontologie ENERGIE, Apache Jena Fuseki, SPARQL, RDFLib |
| Interface | Tailwind CSS, JavaScript, esbuild, Lucide, Chart.js, Cytoscape.js |

## Prise en main

### Prérequis

- Python 3.13 ou version ultérieure et [uv](https://docs.astral.sh/uv/)
- Node.js et npm
- Apache Jena Fuseki, installé séparément ou lancé avec Docker Compose

### Installation et lancement

Depuis la racine du dépôt, installez les dépendances Python et frontend verrouillées, puis générez les fichiers statiques :

```powershell
uv sync
npm ci
npm run build
```

Configurez les variables d'environnement décrites ci-dessous dans votre terminal ou votre environnement de déploiement. Pour le développement local avec Django, `DJANGO_DEBUG=true` active la clé secrète de repli réservée au développement. En production, définissez une valeur privée pour `DJANGO_SECRET_KEY` et laissez `DJANGO_DEBUG=false`.

Pour démarrer le service Fuseki inclus, définissez d'abord `FUSEKI_ADMIN_PASSWORD` dans l'environnement. Le fichier `docker-compose.yml` exige cette variable et conserve les données Fuseki dans un volume Docker :

```powershell
$env:FUSEKI_ADMIN_PASSWORD = "remplacer-par-un-mot-de-passe-local"
docker compose up -d
```

Chargez l'ontologie ENERGIE et les données RDF de l'application dans le jeu de données Fuseki configuré. Démarrez ensuite Django :

```powershell
$env:DJANGO_DEBUG = "true"
uv run python manage.py runserver
```

Ouvrez `http://127.0.0.1:8000/`. N'utilisez pas le mot de passe d'exemple dans un déploiement réel : privilégiez un gestionnaire de secrets ou un autre mécanisme privé de gestion des variables d'environnement.

## Configuration

Le fichier `.env` du dépôt n'est volontairement pas fourni. Les fichiers `.env` locaux sont ignorés par Git ; configurez plutôt les valeurs dans votre terminal ou votre environnement de déploiement.

| Variable | Rôle | Valeur par défaut |
| --- | --- | --- |
| `DJANGO_DEBUG` | Active le mode de développement Django | `false` |
| `DJANGO_SECRET_KEY` | Clé de signature Django ; obligatoire si le mode debug est désactivé | Vide |
| `DJANGO_ALLOWED_HOSTS` | Noms d'hôtes autorisés, séparés par des virgules | `localhost` |
| `FUSEKI_URL` | URL de base du serveur Fuseki | `http://127.0.0.1:3030` |
| `FUSEKI_DATASET` | Nom du jeu de données Fuseki | `energy` |
| `FUSEKI_QUERY_URL` | Point de terminaison SPARQL de requête explicite ; remplace l'URL calculée | Calculé à partir de `FUSEKI_URL` et `FUSEKI_DATASET` |
| `FUSEKI_UPDATE_URL` | Point de terminaison SPARQL de mise à jour explicite ; remplace l'URL calculée | Calculé à partir de `FUSEKI_URL` et `FUSEKI_DATASET` |
| `SPARQL_ENDPOINT` | Ancienne variable de repli pour le point de terminaison de requête | Vide |
| `FUSEKI_ADMIN_USER` / `FUSEKI_ADMIN_PASSWORD` | Identifiants HTTP Basic facultatifs pour Fuseki ; le mot de passe est requis par le service Compose inclus | Vides |
| `USE_MOCK_RDF` | Active les données RDF simulées pour les vues en lecture seule compatibles | `false` |

Pour les requêtes, l'ordre de priorité est `FUSEKI_QUERY_URL`, puis `SPARQL_ENDPOINT`, puis `FUSEKI_URL` associé à `FUSEKI_DATASET`. Par défaut, le point de terminaison de mise à jour est construit à partir de `FUSEKI_URL` et `FUSEKI_DATASET`.

## Routes principales

- `/` — page d'accueil publique
- `/workspace/` — vue d'ensemble et répartition des classes depuis Fuseki
- `/graph/` — explorateur de graphe RDF avec résultats limités
- `/graph/data/` — point de terminaison JSON du graphe, limité à 180 résultats RDF
- `/questions/` — questions-réponses en langage naturel
- `/creation/` — aperçu et confirmation de création RDF
- `/admin/` — administration Django

Les résultats du système de questions-réponses sont plafonnés séparément à 100. Les limites de l'API du graphe et des requêtes TALN protègent chacune leur fonctionnalité.

## Ressources frontend

Après toute modification des templates, des styles ou du JavaScript, régénérez les fichiers statiques :

```powershell
npm ci
npm run build
```

Tailwind CSS analyse les templates Django. La compilation regroupe les icônes Lucide et charge Chart.js à la demande dans la vue d'ensemble, ainsi que Cytoscape.js dans l'explorateur de graphe. Les fichiers générés sont servis depuis `src/web_sem/static/web_sem/`.
