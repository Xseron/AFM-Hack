import { escapeHtml } from "../util.js";

export function riskClass(score) {
  if (typeof score !== "number") return "warn";
  if (score >= 0.66) return "scam";
  if (score >= 0.33) return "warn";
  return "clean";
}

export function categoryBadge(category) {
  const c = category || "-";
  const cls = c && c !== "clean" && c !== "-" ? "scam" : "clean";
  return `<span class="badge ${cls}">${escapeHtml(c)}</span>`;
}

export function confidenceBar(value) {
  const pct = typeof value === "number" ? Math.round(value * 100) : 0;
  return `<div class="bar" title="${pct}%"><i style="width:${pct}%"></i></div>`;
}
