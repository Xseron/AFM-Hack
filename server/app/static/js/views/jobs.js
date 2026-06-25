import { api, fmt } from "../api.js";
import { escapeHtml, fmtTime } from "../util.js";
import { categoryBadge, verdictBadge } from "../components/riskBadge.js";

let timer = null;
let items = [];
const filters = { status: "", category: "", minRisk: 0, q: "" };

export function render(mount) {
  mount.innerHTML = `
    <section class="card">
      <h2>Jobs</h2>
      <div class="row">
        <select id="fStatus"><option value="">any status</option>
          <option>queued</option><option>triage</option><option>analysis</option>
          <option>done</option><option>failed</option></select>
        <select id="fCategory"><option value="">any category</option>
          <option>gambling</option><option>pyramid</option><option>fraud</option><option>clean</option></select>
        <label>min risk <input id="fRisk" type="number" min="0" max="100" step="5" value="0" style="width:80px"></label>
        <input id="fQ" placeholder="search description / shortcode" style="flex:1;min-width:200px">
      </div>
    </section>
    <section class="card">
      <table>
        <thead><tr><th>Time</th><th>Reel</th><th>Description</th><th>Status</th><th>Risk</th><th>Verdict</th><th>Category</th></tr></thead>
        <tbody id="rows"><tr><td colspan="7" class="muted">Loading…</td></tr></tbody>
      </table>
    </section>`;

  const bind = (id, key, transform = (v) => v) =>
    mount.querySelector(id).addEventListener("input", (e) => { filters[key] = transform(e.target.value); draw(mount); });
  bind("#fStatus", "status");
  bind("#fCategory", "category");
  bind("#fRisk", "minRisk", (v) => (parseFloat(v) || 0) / 100);
  bind("#fQ", "q", (v) => v.toLowerCase());

  load(mount);
  timer = setInterval(() => load(mount), 3000);
}

export function stop() { if (timer) clearInterval(timer); timer = null; }

async function load(mount) {
  try {
    const [recent, review] = await Promise.all([
      api("/recent-jobs?limit=200").catch(() => ({ items: [] })),
      api("/review-queue?limit=200").catch(() => ({ items: [] })),
    ]);
    const byId = new Map();
    for (const it of recent.items || []) byId.set(it.job_id, it);
    for (const it of review.items || []) byId.set(it.job_id, it);
    items = [...byId.values()].sort((a, b) => (b.created_at || "").localeCompare(a.created_at || ""));
    draw(mount);
  } catch (_) {}
}

function match(it) {
  if (filters.status && it.status !== filters.status) return false;
  if (filters.category && (it.category || "") !== filters.category) return false;
  if (filters.minRisk && !(typeof it.risk_score === "number" && it.risk_score >= filters.minRisk)) return false;
  if (filters.q) {
    const hay = `${it.description || ""} ${(it.source && it.source.shortcode) || ""}`.toLowerCase();
    if (!hay.includes(filters.q)) return false;
  }
  return true;
}

function draw(mount) {
  const rows = items.filter(match).map((it) => {
    const sc = (it.source && (it.source.shortcode || it.source.platform)) || "-";
    const url = it.source && (it.source.top_bar_url || it.source.url || it.source.permalink);
    const reel = url ? `<a href="${escapeHtml(url)}" target="_blank" rel="noreferrer">${escapeHtml(sc)}</a>` : escapeHtml(sc);
    return `<tr class="clickable" onclick="location.hash='#/jobs/${encodeURIComponent(it.job_id)}'">
      <td>${fmtTime(it.created_at)}</td><td>${reel}</td>
      <td>${escapeHtml((it.description || "").slice(0, 80))}</td>
      <td>${escapeHtml(it.status || "")}</td>
      <td>${fmt(it.risk_score)}</td>
      <td>${verdictBadge(it.verdict, it.category)}</td>
      <td>${categoryBadge(it.category)}</td></tr>`;
  });
  mount.querySelector("#rows").innerHTML = rows.length
    ? rows.join("") : '<tr><td colspan="7" class="muted">No matching jobs.</td></tr>';
}
