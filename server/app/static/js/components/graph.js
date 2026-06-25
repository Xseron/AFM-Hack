const TYPE_COLOR = {
  account: "#ff7a3d", domain: "#34d4ff", telegram: "#2bd97a",
  phone: "#ffc24b", email: "#c792ea", wallet: "#f78c6c",
  social: "#82aaff", avatar: "#ff5a72",
};

export function renderGraph(container, nodes, edges) {
  container.innerHTML = "";
  if (!window.cytoscape) { container.innerHTML = '<p class="muted">Graph library not loaded.</p>'; return; }
  if (!nodes || !nodes.length) { container.innerHTML = '<p class="muted">No graph data yet.</p>'; return; }
  const elements = [
    ...nodes.map((n) => ({ data: { id: n.id, label: n.label || n.id, type: n.type } })),
    ...edges.map((e) => ({ data: { source: e.source, target: e.target, label: e.kind } })),
  ];
  window.cytoscape({
    container,
    elements,
    style: [
      { selector: "node", style: {
        "background-color": (n) => TYPE_COLOR[n.data("type")] || "#8a94a6",
        label: "data(label)", color: "#e9edf4", "font-size": 10,
        "font-family": "Fira Code, monospace",
        "text-valign": "center", "text-halign": "right", "text-margin-x": 5 } },
      { selector: "edge", style: {
        width: 1.5, "line-color": "#2a3340", "curve-style": "bezier" } },
    ],
    layout: { name: "cose", animate: false },
  });
}
