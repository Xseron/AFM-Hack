import { escapeHtml } from "../util.js";
import { confidenceBar } from "./riskBadge.js";

const MODALITY_ICON = { text: "Aa", audio: "♪", ocr: "▣", visual: "◉", triage: "⚑" };

export function findingsHtml(findings) {
  const list = findings || [];
  if (!list.length) return '<p class="muted">No findings.</p>';
  const groups = {};
  for (const f of list) (groups[f.modality || "other"] ||= []).push(f);
  return Object.entries(groups).map(([modality, items]) => `
    <div class="card">
      <h2>${MODALITY_ICON[modality] || "•"} ${escapeHtml(modality)}</h2>
      ${items.map(findingCard).join("")}
    </div>`).join("");
}

function findingCard(f) {
  const ts = typeof f.ts_in_video === "number" ? ` @ ${f.ts_in_video.toFixed(1)}s` : "";
  const conf = typeof f.confidence === "number" ? f.confidence.toFixed(3) : "-";
  return `
    <div class="finding">
      <div class="row" style="justify-content:space-between">
        <strong>${escapeHtml(f.signal_type || "")}${ts}</strong>
        <span class="muted">${conf}</span>
      </div>
      ${confidenceBar(f.confidence)}
      <details><summary>evidence</summary>
        <pre>${escapeHtml(JSON.stringify(f.evidence || {}, null, 2))}</pre>
      </details>
    </div>`;
}
