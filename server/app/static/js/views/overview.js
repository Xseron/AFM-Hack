import { api, fmt } from "../api.js";
import { escapeHtml, fmtTime } from "../util.js";
import { categoryBadge, verdictBadge } from "../components/riskBadge.js";

let timer = null;

export function render(mount) {
  mount.innerHTML = `
    <section class="card"><h2>Overview</h2><div id="kpis" class="kpis"></div></section>
    <section class="card"><h2>Recent activity</h2>
      <table><thead><tr><th>Time</th><th>Reel</th><th>Status</th><th>Risk</th><th>Verdict</th><th>Category</th></tr></thead>
      <tbody id="recent"><tr><td colspan="6" class="muted">Loading…</td></tr></tbody></table></section>`;
  load(mount);
  timer = setInterval(() => load(mount), 3000);
}

export function stop() { if (timer) clearInterval(timer); timer = null; }

async function load(mount) {
  try {
    const [recent, review, parser] = await Promise.all([
      api("/recent-jobs?limit=200").catch(() => ({ items: [] })),
      api("/review-queue?limit=200").catch(() => ({ items: [] })),
      api("/parser/status").catch(() => ({ running: false })),
    ]);
    const items = recent.items || [];
    const scam = items.filter((it) => (it.verdict || it.category) === "scam").length;
    const semi = items.filter((it) => it.verdict === "semi_scam").length;
    const risks = items.map((it) => it.risk_score).filter((v) => typeof v === "number");
    const avg = risks.length ? risks.reduce((a, b) => a + b, 0) / risks.length : null;
    const kpis = [
      ["Total jobs", items.length],
      ["Flagged scam", scam],
      ["Semi-scam", semi],
      ["Avg risk", fmt(avg)],
      ["Review queue", (review.items || []).length],
      ["Parser", parser.running ? "running" : "idle"],
    ];
    mount.querySelector("#kpis").innerHTML = kpis.map(([k, v]) => `<div class="kpi"><span>${k}</span><strong>${escapeHtml(v)}</strong></div>`).join("");
    mount.querySelector("#recent").innerHTML = items.slice(0, 15).map((it) => {
      const sc = (it.source && (it.source.shortcode || it.source.platform)) || "-";
      return `<tr class="clickable" onclick="location.hash='#/jobs/${encodeURIComponent(it.job_id)}'">
        <td>${fmtTime(it.created_at)}</td><td>${escapeHtml(sc)}</td>
        <td>${escapeHtml(it.status || "")}</td><td>${fmt(it.risk_score)}</td>
        <td>${verdictBadge(it.verdict, it.category)}</td><td>${categoryBadge(it.category)}</td></tr>`;
    }).join("") || '<tr><td colspan="6" class="muted">No jobs yet.</td></tr>';
  } catch (_) {}
}
