# SmartGrid — Energy Intelligence Platform

SmartGrid is a Django application for exploring the ENERGIE ontology and RDF individuals stored in Apache Jena Fuseki. The public landing page is at `/`; the data-backed workspace starts at `/workspace/`. Existing ontology CRUD routes and French NLP question answering remain server-rendered Django pages.

## Frontend assets

Install the pinned frontend dependencies and build the local static assets after changing templates, styles, or JavaScript:

```powershell
npm ci
npm run build
```

Tailwind CSS scans the Django templates. The build bundles Lucide icons and lazy-loads Chart.js on the overview and Cytoscape.js on the graph explorer. Generated files are served from `src/web_sem/static/web_sem/`.

## Main routes

- `/` — public SmartGrid landing page
- `/workspace/` — Fuseki-backed overview and class distribution
- `/graph/` — bounded, read-only RDF graph explorer
- `/graph/data/` — graph JSON endpoint, limited to 180 RDF results
- `/questions/` — French natural-language question answering
- `/creation/` — preview and confirmation flow for RDF individual creation
- `/admin/` — Django administration, themed with Django Unfold

Configure Fuseki through the existing Django environment settings. Dashboard counts and graph content are queried from that configured dataset; no sample individuals or energy measurements are added by the frontend.