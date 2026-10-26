import cytoscape from "cytoscape";

export function initializeKnowledgeGraph() {
  const graphContainer = document.getElementById("knowledge-graph");
  const state = document.getElementById("graph-state");
  const count = document.getElementById("graph-count");
  const truncation = document.getElementById("graph-truncation");
  const classFilter = document.getElementById("graph-class-filter");
  const searchInput = document.getElementById("graph-search");
  const detailEmpty = document.getElementById("graph-detail-empty");
  const detailValues = document.getElementById("graph-detail-values");
  let graph;

  const showState = (message, kind) => {
    state.hidden = false;
    state.classList.toggle("is-error", kind === "error");
    state.classList.toggle("is-empty", kind === "empty");
    state.querySelector("span:last-child").textContent = message;
  };

  const showDetails = (node) => {
    const data = node.data();
    document.getElementById("detail-label").textContent = data.label || "—";
    document.getElementById("detail-kind").textContent =
      data.kind === "individual" ? "Individu" :
      data.kind === "class" ? "Classe" :
      data.kind === "literal" ? "Valeur littérale" : "Ressource";
    document.getElementById("detail-class").textContent = data.class || "—";
    document.getElementById("detail-iri").textContent = data.detail || data.id;
    detailEmpty.hidden = true;
    detailValues.hidden = false;
  };

  const applySearch = () => {
    if (!graph) return;
    const term = searchInput.value.trim().toLocaleLowerCase("fr");
    graph.batch(() => {
      graph.nodes().forEach((node) => {
        const match =
          !term ||
          `${node.data("label")} ${node.data("class")}`.toLocaleLowerCase("fr").includes(term);
        node.style("display", match ? "element" : "none");
      });
      graph.edges().forEach((edge) => {
        const visible =
          edge.source().style("display") !== "none" &&
          edge.target().style("display") !== "none";
        edge.style("display", visible ? "element" : "none");
      });
    });
  };

  const loadGraph = async () => {
    showState("Chargement des données RDF…", "loading");
    count.textContent = "—";
    truncation.hidden = true;
    const url = new URL(graphContainer.dataset.source, window.location.origin);
    if (classFilter.value) url.searchParams.set("class", classFilter.value);

    try {
      const response = await fetch(url, { headers: { Accept: "application/json" } });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || "Le graphe RDF est indisponible.");
      if (graph) graph.destroy();

      const elements = [...payload.nodes, ...payload.edges];
      if (elements.length === 0) {
        count.textContent = "0";
        showState("Aucun individu ou relation ne correspond à ce filtre.", "empty");
        return;
      }
      state.hidden = true;
      graph = cytoscape({
        container: graphContainer,
        elements,
        minZoom: 0.2,
        maxZoom: 3,
        style: [
          {
            selector: "node",
            style: {
              label: "data(label)",
              color: "#e7f2ec",
              "font-family": "Segoe UI, sans-serif",
              "font-size": 10,
              "text-wrap": "ellipsis",
              "text-max-width": 92,
              "text-valign": "bottom",
              "text-margin-y": 7,
              "background-color": "#52d99d",
              "border-color": "#9af2cb",
              "border-width": 1,
              width: 26,
              height: 26,
              "text-outline-color": "#0c1713",
              "text-outline-width": 2,
            },
          },
          {
            selector: 'node[kind = "class"]',
            style: {
              "background-color": "#80a7ff",
              "border-color": "#b5ccff",
              shape: "round-rectangle",
              width: 30,
              height: 20,
            },
          },
          {
            selector: 'node[kind = "literal"]',
            style: {
              "background-color": "#d7a65d",
              "border-color": "#f1d09c",
              shape: "diamond",
              width: 18,
              height: 18,
              "font-size": 9,
            },
          },
          {
            selector: 'node[kind = "resource"]',
            style: { "background-color": "#ad8ee7", "border-color": "#d2c0ff" },
          },
          {
            selector: "node:selected",
            style: { "border-color": "#ffffff", "border-width": 3, "overlay-opacity": 0.08 },
          },
          {
            selector: "edge",
            style: {
              width: 1,
              "line-color": "#53685d",
              "target-arrow-color": "#79d7a8",
              "target-arrow-shape": "triangle",
              "curve-style": "bezier",
              label: "data(label)",
              color: "#9eb2a6",
              "font-family": "Segoe UI, sans-serif",
              "font-size": 8,
              "text-rotation": "autorotate",
              "text-background-color": "#0b1713",
              "text-background-opacity": 0.88,
              "text-background-padding": 2,
            },
          },
        ],
        layout: {
          name: "cose",
          animate: false,
          nodeRepulsion: 5200,
          idealEdgeLength: 110,
          padding: 48,
        },
      });
      count.textContent = String(payload.nodes.length);
      truncation.hidden = !payload.truncated;
      graph.on("tap", "node", (event) => showDetails(event.target));
      applySearch();
    } catch (error) {
      showState(error instanceof Error ? error.message : "Le graphe RDF est indisponible.", "error");
    }
  };

  classFilter.addEventListener("change", loadGraph);
  searchInput.addEventListener("input", applySearch);
  document.getElementById("graph-reset").addEventListener("click", () => {
    classFilter.value = "";
    searchInput.value = "";
    loadGraph();
  });
  document.getElementById("graph-fit").addEventListener("click", () => graph?.fit(undefined, 50));
  document.getElementById("graph-zoom-in").addEventListener("click", () =>
    graph?.zoom({
      level: graph.zoom() * 1.25,
      renderedPosition: { x: graph.width() / 2, y: graph.height() / 2 },
    }),
  );
  document.getElementById("graph-zoom-out").addEventListener("click", () =>
    graph?.zoom({
      level: graph.zoom() / 1.25,
      renderedPosition: { x: graph.width() / 2, y: graph.height() / 2 },
    }),
  );
  loadGraph();
}
