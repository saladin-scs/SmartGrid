import {
  Activity,
  ArrowUpRight,
  BatteryCharging,
  Boxes,
  Cable,
  ChartNoAxesCombined,
  CircleAlert,
  CircleCheck,
  createIcons,
  Database,
  Factory,
  FileText,
  GitBranch,
  Info,
  LayoutDashboard,
  MapPin,
  Maximize2,
  MessagesSquare,
  MousePointer2,
  Network,
  PanelLeftClose,
  PanelLeftOpen,
  Pencil,
  Plus,
  RotateCcw,
  Save,
  ScanSearch,
  Search,
  Settings,
  ShieldCheck,
  Sparkles,
  Truck,
  UserRound,
  Users,
  X,
  Trash2,
  Zap,
  ZoomIn,
  ZoomOut,
} from "lucide";

const iconSet = {
  Activity,
  ArrowUpRight,
  BatteryCharging,
  Boxes,
  Cable,
  ChartNoAxesCombined,
  CircleAlert,
  CircleCheck,
  Database,
  Factory,
  FileText,
  GitBranch,
  Info,
  LayoutDashboard,
  MapPin,
  Maximize2,
  MessagesSquare,
  MousePointer2,
  Network,
  PanelLeftClose,
  PanelLeftOpen,
  Pencil,
  Plus,
  RotateCcw,
  Save,
  ScanSearch,
  Search,
  Settings,
  ShieldCheck,
  Sparkles,
  Truck,
  UserRound,
  Users,
  X,
  Trash2,
  Zap,
  ZoomIn,
  ZoomOut,
};

createIcons({ icons: iconSet, attrs: { "stroke-width": 1.8 } });

const workspace = document.getElementById("workspace-shell");
const sidebarToggle = document.getElementById("sidebar-toggle");
if (workspace && sidebarToggle) {
  const sidebarBackdrop = document.getElementById("sidebar-backdrop");
  const compactNavigation = window.matchMedia("(max-width: 900px)");
  const setExpanded = (expanded) => {
    sidebarToggle.setAttribute("aria-expanded", String(expanded));
    sidebarToggle.setAttribute("aria-label", expanded ? "Réduire le menu" : "Ouvrir le menu");
  };
  const applyNavigationMode = () => {
    if (compactNavigation.matches) {
      workspace.classList.remove("is-collapsed");
      setExpanded(false);
      return;
    }
    const saved = window.localStorage.getItem("smartgrid-sidebar-collapsed") === "true";
    workspace.classList.toggle("is-collapsed", saved);
    setExpanded(!saved);
  };
  applyNavigationMode();
  compactNavigation.addEventListener("change", applyNavigationMode);
  sidebarToggle.addEventListener("click", () => {
    if (compactNavigation.matches) {
      const expanded = workspace.classList.toggle("is-collapsed");
      setExpanded(expanded);
      return;
    }
    const collapsed = workspace.classList.toggle("is-collapsed");
    setExpanded(!collapsed);
    window.localStorage.setItem("smartgrid-sidebar-collapsed", String(collapsed));
  });
  sidebarBackdrop?.addEventListener("click", () => {
    workspace.classList.remove("is-collapsed");
    setExpanded(false);
    sidebarToggle.focus();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && compactNavigation.matches && workspace.classList.contains("is-collapsed")) {
      workspace.classList.remove("is-collapsed");
      setExpanded(false);
      sidebarToggle.focus();
    }
  });
}

if (document.getElementById("type-distribution-chart")) {
  import("./dashboard.js")
    .then(({ initializeDashboard }) => initializeDashboard())
    .catch(() => {
      const container = document.querySelector(".chart-container");
      const message = document.createElement("p");
      message.className = "empty";
      message.textContent = "La visualisation des classes n’a pas pu être chargée.";
      container?.append(message);
    });
}

if (document.getElementById("knowledge-graph")) {
  import("./graph.js")
    .then(({ initializeKnowledgeGraph }) => initializeKnowledgeGraph())
    .catch(() => {
      const state = document.getElementById("graph-state");
      state.hidden = false;
      state.classList.add("is-error");
      state.querySelector("span:last-child").textContent = "L’explorateur de graphe n’a pas pu être chargé.";
    });
}
