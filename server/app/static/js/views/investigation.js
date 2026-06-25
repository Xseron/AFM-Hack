import { api, postJson } from "../api.js";
import { escapeHtml } from "../util.js";
import { renderGraph } from "../components/graph.js";

let jobTimer = null;

export function render(mount) {
  mount.innerHTML = `
    <section class="card">
      <h2>OSINT — scan accounts</h2>
      <div class="row">
        <input id="usernames" placeholder="comma-separated usernames" style="flex:1;min-width:240px">
        <button id="scanBtn" type="button">Scan</button>
      </div>
      <div id="osintStatus" class="muted"></div>
      <div id="profiles"></div>
    </section>

    <section class="card">
      <h2>Investigation graph</h2>
      <div class="row"><label>min shared <input id="minShared" type="number" min="1" value="2" style="width:80px"></label>
        <button id="reloadGraph" type="button" class="secondary">Reload</button></div>
      <div id="graph" class="graph"></div>
    </section>

    <section class="card"><h2>Telegram channels</h2><div id="telegram" class="muted">Loading…</div></section>`;

  mount.querySelector("#scanBtn").addEventListener("click", () => startScan(mount));
  mount.querySelector("#reloadGraph").addEventListener("click", () => loadGraph(mount));
  loadGraph(mount);
  loadTelegram(mount);
}

export function stop() { if (jobTimer) clearInterval(jobTimer); jobTimer = null; }

async function startScan(mount) {
  const status = mount.querySelector("#osintStatus");
  const names = mount.querySelector("#usernames").value.split(",").map((s) => s.trim()).filter(Boolean);
  if (!names.length) { status.textContent = "Enter at least one username."; return; }
  const res = await postJson("/osint/accounts", { usernames: names });
  if (!res.available) { status.textContent = `Investigator offline: ${res.reason || ""}`; return; }
  status.textContent = `Scanning ${res.accepted ?? names.length} account(s)…`;
  if (jobTimer) clearInterval(jobTimer);
  jobTimer = setInterval(() => pollJob(mount, res.job_id, status), 2000);
}

async function pollJob(mount, jobId, status) {
  const res = await api(`/osint/accounts/${encodeURIComponent(jobId)}`);
  if (!res.available) { status.textContent = "Investigator offline."; stop(); return; }
  renderProfiles(mount, res.results || []);
  if (res.status === "done") { status.textContent = "Scan complete."; stop(); loadGraph(mount); }
  else status.textContent = `Scanning… (${res.done || 0}/${res.accepted || "?"})`;
}

function renderProfiles(mount, results) {
  mount.querySelector("#profiles").innerHTML = results.map((p) => {
    const o = p.osint || {};
    const chips = (label, arr) => (arr && arr.length) ? `<div><span class="muted">${label}:</span> ${arr.map(escapeHtml).join(", ")}</div>` : "";
    return `<div class="finding">
      <strong>@${escapeHtml(p.username || "")} <span class="muted">${escapeHtml(p.status || "")}</span></strong>
      ${p.full_name ? `<div>${escapeHtml(p.full_name)}</div>` : ""}
      ${chips("phones", o.phones)}${chips("emails", o.emails)}${chips("wallets", o.crypto_wallets)}
      ${chips("socials", o.accounts_found)}${chips("telegram", p.telegram_links)}
      ${o.domain ? `<div><span class="muted">domain:</span> ${escapeHtml(o.domain)} ${o.domain_age_days != null ? `(${o.domain_age_days}d)` : ""}</div>` : ""}
    </div>`;
  }).join("") || "";
}

async function loadGraph(mount) {
  const container = mount.querySelector("#graph");
  const minShared = parseInt(mount.querySelector("#minShared").value, 10) || 2;
  const res = await api(`/osint/graph?min_shared=${minShared}`);
  if (!res.available) { container.innerHTML = `<p class="banner">Investigator offline: ${escapeHtml(res.reason || "")}</p>`; return; }
  renderGraph(container, res.nodes || [], res.edges || []);
}

async function loadTelegram(mount) {
  const box = mount.querySelector("#telegram");
  const res = await api("/telegram/channels");
  if (!res.available) { box.innerHTML = `<p class="banner">Telegram crawler offline: ${escapeHtml(res.reason || "")}</p>`; return; }
  const channels = res.items || [];
  box.innerHTML = channels.length ? channels.map((c) => `
    <div class="finding">
      <div class="row" style="justify-content:space-between">
        <strong>${escapeHtml(c.title || c.username || "")}</strong>
        <span class="badge ${c.risk_score >= 66 ? "scam" : c.risk_score >= 33 ? "warn" : "clean"}">risk ${escapeHtml(c.risk_score)}</span>
      </div>
      <div class="muted">${escapeHtml((c.categories || []).join(", "))}</div>
      <p>${escapeHtml(c.explanation || "")}</p>
    </div>`).join("") : '<p class="muted">No channels analyzed yet.</p>';
}
