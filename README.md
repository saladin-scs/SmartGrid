# SmartGrid

SmartGrid is an ontology-driven energy information platform. It combines a Django web application, the ENERGIE RDF ontology, and Apache Jena Fuseki to explore energy-system data through dashboards, a graph browser, semantic search, and natural-language questions.

## What makes the AI different

SmartGrid's AI is **grounded, inspectable, and domain-specific**. It does not ask a generative language model to invent an answer: it translates a user's question into a constrained query over the ENERGIE knowledge graph, then presents the data returned by Fuseki.

The French-first NLP pipeline uses spaCy's `fr_core_news_sm` model for tokenization and lemmatization, with a lightweight fallback when the model is unavailable. Ontology class names and curated French and English aliases connect everyday phrasing to the concepts and relationships defined in the RDF schema.

### Natural-language question pipeline

1. **Normalize** the question: collapse whitespace, remove accents and punctuation for matching, and lemmatize tokens.
2. **Interpret** language cues and domain terms to identify an intent such as listing individuals, counting instances, listing class types, retrieving details, or querying by zone and relation.
3. **Ground** class, property, zone, and individual references against the ontology catalog and, where needed, the Fuseki dataset. Ambiguous or unresolved questions can request clarification.
4. **Build and validate** an ontology-templated SPARQL `SELECT`. The question text is not interpolated into the query; generated question-answering queries are read-only, ontology-scoped, and result-limited.
5. **Execute and explain** the query through the shared Fuseki client, then format returned bindings as results with a plain-language explanation.

Example questions include *« Combien de centrales nucléaires existe-t-il ? »*, *« Quels techniciens travaillent à Sfax ? »*, and *“How many nuclear plants are there?”*. This is semantic parsing and knowledge-graph question answering—not open-domain chat—and answers depend on the ontology and data currently available in Fuseki.

The separate natural-language creation workflow extracts ontology properties from a description and shows an RDF preview. It writes only after the user reviews and explicitly confirms the preview.

## Features

- Django workspace for ENERGIE ontology classes and RDF individuals.
- Fuseki-backed overview, class distribution, and bounded, read-only RDF graph explorer.
- French-first, bilingual-cue natural-language question answering over the ontology.
- Preview-and-confirm flow for natural-language RDF individual creation.
- Server-rendered Django pages with Tailwind CSS, Lucide icons, Chart.js, and Cytoscape.js.
- Django administration styled with Django Unfold.

## Technology

| Area | Technologies |
| --- | --- |
| Web application | Python 3.13+, Django 5.2, Django Cotton |
| NLP | spaCy, `fr_core_news_sm`, lemmatization, ontology aliases and intent classification |
| Semantic data | RDF, ENERGIE ontology, Apache Jena Fuseki, SPARQL, RDFLib |
| Frontend | Tailwind CSS, JavaScript, esbuild, Lucide, Chart.js, Cytoscape.js |

## Getting started

### Prerequisites

- Python 3.13 or newer and [uv](https://docs.astral.sh/uv/)
- Node.js and npm
- Apache Jena Fuseki, either installed separately or run with Docker Compose

### Install and run

From the repository root, install the locked Python and frontend dependencies and build the static assets:

```powershell
uv sync
npm ci
npm run build
```

Configure the environment variables below in your shell or deployment environment. For local Django development, `DJANGO_DEBUG=true` enables the development-only fallback secret key; production must set a private `DJANGO_SECRET_KEY` and keep `DJANGO_DEBUG=false`.

To start the bundled Fuseki service, set `FUSEKI_ADMIN_PASSWORD` in the environment first; `docker-compose.yml` requires it and persists Fuseki data in a Docker volume:

```powershell
$env:FUSEKI_ADMIN_PASSWORD = "replace-with-a-local-password"
docker compose up -d
```

Load the ENERGIE ontology and any application RDF data into the configured Fuseki dataset. Then start Django:

```powershell
$env:DJANGO_DEBUG = "true"
uv run python manage.py runserver
```

Open `http://127.0.0.1:8000/`. Do not use the example password in a real deployment; use a secret manager or another private environment-variable mechanism instead.

## Configuration

The repository's `.env` file is intentionally not included. Local `.env` files are ignored by Git; configure values in your shell or deployment environment instead.

| Variable | Purpose | Default |
| --- | --- | --- |
| `DJANGO_DEBUG` | Enables Django development mode | `false` |
| `DJANGO_SECRET_KEY` | Django signing key; required when debug is disabled | Empty |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated allowed host names | `localhost` |
| `FUSEKI_URL` | Fuseki server base URL | `http://127.0.0.1:3030` |
| `FUSEKI_DATASET` | Fuseki dataset name | `energy` |
| `FUSEKI_QUERY_URL` | Explicit SPARQL query endpoint; overrides the derived endpoint | Derived from `FUSEKI_URL` and `FUSEKI_DATASET` |
| `FUSEKI_UPDATE_URL` | Explicit SPARQL update endpoint; overrides the derived endpoint | Derived from `FUSEKI_URL` and `FUSEKI_DATASET` |
| `SPARQL_ENDPOINT` | Legacy query endpoint fallback | Empty |
| `FUSEKI_ADMIN_USER` / `FUSEKI_ADMIN_PASSWORD` | Optional Fuseki HTTP Basic credentials; the password is required by the bundled Compose service | Empty |
| `USE_MOCK_RDF` | Enables mock RDF data for supported read-only views | `false` |

The query endpoint precedence is `FUSEKI_QUERY_URL`, then `SPARQL_ENDPOINT`, then `FUSEKI_URL` plus `FUSEKI_DATASET`. The update endpoint defaults to `FUSEKI_URL` plus `FUSEKI_DATASET`.

## Main routes

- `/` — public landing page
- `/workspace/` — Fuseki-backed overview and class distribution
- `/graph/` — bounded RDF graph explorer
- `/graph/data/` — graph JSON endpoint, limited to 180 RDF results
- `/questions/` — natural-language question answering
- `/creation/` — RDF creation preview and confirmation
- `/admin/` — Django administration

Question-answering results are separately capped at 100. The graph endpoint and NLP query limits are safeguards for their respective features.

## Frontend assets

After changing templates, styles, or JavaScript, rebuild the local static assets:

```powershell
npm ci
npm run build
```

Tailwind CSS scans the Django templates. The build bundles Lucide icons and lazy-loads Chart.js on the overview and Cytoscape.js on the graph explorer. Generated files are served from `src/web_sem/static/web_sem/`.
