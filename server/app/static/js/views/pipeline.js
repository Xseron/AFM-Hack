import { api, postJson } from "../api.js";
import { escapeHtml } from "../util.js";

let archData = null;

export function render(mount) {
  mount.innerHTML = `
    <section class="card">
      <h2>Pipeline architecture</h2>
      <p class="muted">Left to right. A reel is flagged scam when any checker's confidence reaches its threshold. Toggle checkers, set thresholds, tune the investigator, or reload plugins.</p>
      <div class="row"><button id="reloadPlugins" type="button" class="secondary">Reload plugins</button>
        <span id="pluginsDir" class="muted"></span><span id="archStatus" class="muted"></span></div>
      <div id="flow" class="flow"><span class="muted">Loading pipeline…</span></div>
    </section>`;

  mount.querySelector("#reloadPlugins").addEventListener("click", async () => {
    try { archData = await postJson("/architecture/reload", {}); renderFlow(mount); msg(mount, "Plugins reloaded."); }
    catch (err) { msg(mount, err.message, true); }
  });
  mount.querySelector("#flow").addEventListener("change", (e) => onChange(mount, e));
  mount.querySelector("#flow").addEventListener("click", (e) => onClick(mount, e));
  load(mount);
}

export function stop() {}

function msg(mount, text, bad = false) {
  const s = mount.querySelector("#archStatus");
  s.textContent = text; s.style.color = bad ? "var(--bad)" : "var(--good)";
}

async function load(mount) {
  try { archData = await api("/architecture"); renderFlow(mount); }
  catch (err) { msg(mount, err.message, true); }
}

function pct(v) { return Math.round((v ?? 0) * 100); }

function pipelineNode(n) {
  if (n.error) return `<div class="node err"><div class="node-title">${escapeHtml(n.label)}</div>
    <div class="muted">plugin load error</div><div class="err-msg">${escapeHtml(n.error)}</div></div>`;
  const th = typeof n.threshold === "number"
    ? `<label class="muted">scam ≥ % <input type="number" min="0" max="100" value="${pct(n.threshold)}" data-node-threshold="${escapeHtml(n.id)}" style="width:74px"></label>` : "";
  const del = n.removable ? `<button type="button" class="secondary" data-node-del="${escapeHtml(n.id)}">remove</button>` : "";
  return `<div class="node${n.enabled ? "" : " off"}">
    <div class="node-title">${escapeHtml(n.label)}</div>
    <div class="row"><span class="badge ${n.source === "plugin" ? "" : "clean"}">${escapeHtml(n.source)}</span>${n.checker ? `<span class="badge">${escapeHtml(n.checker)}</span>` : ""}</div>
    <label class="muted"><input type="checkbox" data-node-toggle="${escapeHtml(n.id)}" ${n.enabled ? "checked" : ""}> ${n.enabled ? "enabled" : "disabled"}</label>
    ${th}${del}</div>`;
}

function aggregateNode(n) {
  return `<div class="node"><div class="node-title">Aggregator</div>
    <div class="muted">Scam if any checker reaches its threshold.</div>
    <label class="muted">default ≥ % <input type="number" min="0" max="100" value="${pct(n.default_threshold)}" data-default-threshold style="width:74px"></label></div>`;
}

function investigateNode(n) {
  const th = n.thresholds || {};
  const row = (label, key) => `<label class="muted">${label} % <input type="number" min="0" max="100" value="${pct(th[key])}" data-inv-th="${key}" style="width:74px"></label>`;
  return `<div class="node${n.enabled ? "" : " off"}"><div class="node-title">Investigator</div>
    <label class="muted"><input type="checkbox" data-inv-toggle ${n.enabled ? "checked" : ""}> ${n.enabled ? "ON" : "OFF"}</label>
    <label class="muted">max reels <input type="number" min="1" value="${n.max_reels || ""}" data-inv-max style="width:74px"></label>
    ${row("Semantic", "semantic")}${row("OCR", "ocr")}${row("CLIP", "clip")}${row("Audio", "audio")}</div>`;
}

function stageCol(stage) {
  let body = "";
  if (stage.kind === "info") body = `<div class="node info">${escapeHtml(stage.note || "")}</div>`;
  else if (stage.kind === "pipelines") body = (stage.nodes || []).map(pipelineNode).join("") || '<div class="node info">none</div>';
  else if (stage.kind === "aggregate") body = aggregateNode((stage.nodes || [])[0] || {});
  else if (stage.kind === "investigate") body = investigateNode((stage.nodes || [])[0] || {});
  return `<div class="stage"><div class="stage-head">${escapeHtml(stage.label)}</div>${body}</div>`;
}

function renderFlow(mount) {
  if (!archData) return;
  mount.querySelector("#flow").innerHTML = archData.stages.map(stageCol).join('<div class="stage-arrow">›</div>');
  mount.querySelector("#pluginsDir").textContent = archData.plugins_dir ? `plugins: ${archData.plugins_dir}` : "";
}

async function onChange(mount, e) {
  const d = e.target.dataset; if (!d) return;
  const clamp = () => Math.max(0, Math.min(100, parseFloat(e.target.value) || 0)) / 100;
  try {
    if (d.nodeToggle !== undefined) await postNode(d.nodeToggle, { enabled: e.target.checked });
    else if (d.nodeThreshold !== undefined) await postNode(d.nodeThreshold, { threshold: clamp() });
    else if (d.defaultThreshold !== undefined) await postJson("/architecture/aggregate", { default_threshold: clamp() });
    else if (d.invToggle !== undefined) await postJson("/parser/auto-scan", { enabled: e.target.checked });
    else if (d.invMax !== undefined) { const n = parseInt(e.target.value, 10); await postJson("/parser/auto-scan", { max_reels: n > 0 ? n : 1 }); }
    else if (d.invTh !== undefined) await postJson("/parser/auto-scan", { thresholds: { [d.invTh]: clamp() } });
    else return;
    await load(mount); msg(mount, "Saved.");
  } catch (err) { msg(mount, err.message, true); }
}

async function postNode(id, body) { await postJson(`/architecture/node/${encodeURIComponent(id)}`, body); }

async function onClick(mount, e) {
  const id = e.target.dataset && e.target.dataset.nodeDel;
  if (!id) return;
  if (!confirm(`Remove checker "${id}"? (plugin file stays on disk)`)) return;
  try { const r = await fetch(`/architecture/node/${encodeURIComponent(id)}`, { method: "DELETE" }); if (!r.ok) throw new Error(await r.text()); await load(mount); msg(mount, `Removed ${id}.`); }
  catch (err) { msg(mount, err.message, true); }
}
