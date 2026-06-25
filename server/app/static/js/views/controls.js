import { api, postJson } from "../api.js";
import { escapeHtml } from "../util.js";

let timer = null;

export function render(mount) {
  mount.innerHTML = `
    <section class="card">
      <h2>Upload Video</h2>
      <form id="uploadForm" class="row" style="display:grid;gap:10px">
        <input id="video" type="file" accept="video/*" required>
        <textarea id="description" placeholder="Caption / description" required></textarea>
        <div class="row">
          <button type="submit">Upload &amp; Check</button>
          <button id="clearDedup" type="button" class="secondary">Clear Dedup</button>
        </div>
        <div id="uploadStatus" class="muted"></div>
      </form>
    </section>

    <section class="card">
      <h2>Parser</h2>
      <div class="row" style="display:grid;gap:10px">
        <div class="row">
          <button id="startInstagram" type="button">Start Instagram Reels Parsing</button>
          <button id="startTiktok" type="button">Start TikTok Parsing</button>
          <button id="stopFeed" type="button" class="secondary">Stop</button>
        </div>
        <div class="row">
          <label>IG max sec/video <input id="maxSecInstagram" type="number" min="1" style="width:120px" placeholder="no cap"></label>
          <label>TikTok max sec/video <input id="maxSecTiktok" type="number" min="1" style="width:120px" placeholder="no cap"></label>
        </div>
        <input id="channelUrl" placeholder="https://instagram.com/username/ or @username">
        <div class="row">
          <input id="maxReels" type="number" min="1" placeholder="max reels (server default)">
          <button id="startParser" type="button">Start</button>
          <button id="stopParser" type="button" class="secondary">Stop</button>
        </div>
        <div class="row">
          <input id="feedMax" type="number" min="1" placeholder="feed max (unlimited)">
          <button id="startFeed" type="button" class="secondary">Browse Global Feed</button>
        </div>
        <div class="row">
          <input id="reelUrl" placeholder="https://instagram.com/reel/XXXX/">
          <button id="checkReel" type="button" class="secondary">Check Reel</button>
        </div>
        <div id="parserStatus" class="muted">Checking parser…</div>
      </div>
    </section>

    <section class="card">
      <h2>Auto-Investigate</h2>
      <div class="row">
        <button id="autoScanBtn" type="button" class="secondary">Auto-scan: …</button>
        <label>max/channel <input id="autoMax" type="number" min="1" style="width:90px"></label>
      </div>
      <div class="row" style="margin-top:10px">
        ${["semantic","ocr","clip","audio"].map((k)=>`<label>${k} %
          <input data-th="${k}" type="number" min="0" max="100" style="width:80px"></label>`).join("")}
      </div>
      <div id="autoStatus" class="muted"></div>
    </section>

    <section class="card">
      <h2>Models</h2>
      <div id="modelStatus" class="muted">Loading…</div>
      <div id="models" class="row"></div>
    </section>`;

  wireUpload(mount);
  wireParser(mount);
  wireAutoScan(mount);
  loadModels(mount);
  loadParser(mount);
  timer = setInterval(() => loadParser(mount), 3000);
}

export function stop() { if (timer) clearInterval(timer); timer = null; }

function wireUpload(root) {
  root.querySelector("#uploadForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const status = root.querySelector("#uploadStatus");
    try {
      status.textContent = "Uploading…";
      const fd = new FormData();
      fd.append("video", root.querySelector("#video").files[0]);
      fd.append("description", root.querySelector("#description").value);
      fd.append("source_platform", "manual-ui");
      const data = await api("/videos", { method: "POST", body: fd });
      status.innerHTML = `Queued. <a href="#/jobs/${encodeURIComponent(data.job_id)}">open job</a>`;
    } catch (err) { status.textContent = err.message; }
  });
  root.querySelector("#clearDedup").addEventListener("click", async () => {
    if (!confirm("Clear dedup hashes?")) return;
    const d = await postJson("/dedup/clear", {});
    root.querySelector("#uploadStatus").textContent = `Cleared ${d.cleared} job(s).`;
  });
}

function wireParser(root) {
  const status = root.querySelector("#parserStatus");
  const num = (id) => { const n = parseInt(root.querySelector(id).value, 10); return Number.isNaN(n) ? null : n; };
  // Per-platform recording cap (seconds): TikTok vs Instagram input.
  const maxSec = (platform) => {
    const n = parseFloat(root.querySelector(platform === "tiktok" ? "#maxSecTiktok" : "#maxSecInstagram").value);
    return Number.isNaN(n) || n <= 0 ? null : n;
  };
  const platformOf = (url) => (/tiktok\.com/i.test(url || "") ? "tiktok" : "instagram");
  const startFeed = async (platform, label) => {
    const body = { platform };
    const m = num("#feedMax"); if (m) body.max_reels = m;
    const s = maxSec(platform); if (s) body.max_video_seconds = s;
    status.textContent = `Starting ${label} parsing…`;
    try { renderParser(root, await postJson("/parser/feed", body)); }
    catch (err) { status.textContent = err.message; }
  };
  root.querySelector("#startInstagram").addEventListener("click", () => startFeed("instagram", "Instagram reels"));
  root.querySelector("#startTiktok").addEventListener("click", () => startFeed("tiktok", "TikTok"));
  root.querySelector("#stopFeed").addEventListener("click", async () => {
    try { renderParser(root, await postJson("/parser/stop", {})); } catch (err) { status.textContent = err.message; }
  });
  root.querySelector("#startParser").addEventListener("click", async () => {
    const channel = root.querySelector("#channelUrl").value.trim();
    if (!channel) { status.textContent = "Enter a channel."; return; }
    const body = { channel_url: channel };
    const m = num("#maxReels"); if (m) body.max_reels = m;
    const s = maxSec(platformOf(channel)); if (s) body.max_video_seconds = s;
    try { renderParser(root, await postJson("/parser/start", body)); }
    catch (err) { status.textContent = err.message; }
  });
  root.querySelector("#stopParser").addEventListener("click", async () => {
    try { renderParser(root, await postJson("/parser/stop", {})); } catch (err) { status.textContent = err.message; }
  });
  root.querySelector("#startFeed").addEventListener("click", async () => {
    const body = {}; const m = num("#feedMax"); if (m) body.max_reels = m;
    try { renderParser(root, await postJson("/parser/feed", body)); } catch (err) { status.textContent = err.message; }
  });
  root.querySelector("#checkReel").addEventListener("click", async () => {
    const url = root.querySelector("#reelUrl").value.trim();
    if (!url) { status.textContent = "Paste a reel URL."; return; }
    const body = { reel_url: url };
    const s = maxSec(platformOf(url)); if (s) body.max_video_seconds = s;
    try { renderParser(root, await postJson("/parser/reel", body)); }
    catch (err) { status.textContent = err.message; }
  });
}

function renderParser(root, s) {
  const status = root.querySelector("#parserStatus");
  if (s && s.running) status.textContent = `Running — ${s.channel || ""} (pid ${s.pid || "?"}).`;
  else status.textContent = "Parser idle." + (s && s.browser_running ? " Browser ready." : " Browser will launch on start.");
}

async function loadParser(root) {
  try { renderParser(root, await api("/parser/status")); } catch (_) {}
}

function wireAutoScan(root) {
  const status = root.querySelector("#autoStatus");
  let state = { enabled: false, thresholds: {}, max_reels: 0 };
  const draw = () => {
    root.querySelector("#autoScanBtn").textContent = `Auto-scan: ${state.enabled ? "ON" : "OFF"}`;
    root.querySelectorAll("[data-th]").forEach((i) => {
      if (document.activeElement !== i) i.value = Math.round((state.thresholds[i.dataset.th] ?? 0) * 100);
    });
    const mx = root.querySelector("#autoMax");
    if (document.activeElement !== mx) mx.value = state.max_reels || "";
  };
  const save = async (body) => { state = await postJson("/parser/auto-scan", body); status.textContent = "Saved."; draw(); };
  api("/parser/auto-scan").then((s) => { state = s; draw(); }).catch(() => {});
  root.querySelector("#autoScanBtn").addEventListener("click", () => save({ enabled: !state.enabled }).catch((e) => status.textContent = e.message));
  root.querySelectorAll("[data-th]").forEach((i) =>
    i.addEventListener("change", () => save({ thresholds: { [i.dataset.th]: Math.max(0, Math.min(100, parseFloat(i.value) || 0)) / 100 } }).catch((e) => status.textContent = e.message)));
  root.querySelector("#autoMax").addEventListener("change", () => { const n = parseInt(root.querySelector("#autoMax").value, 10); save({ max_reels: n > 0 ? n : 1 }).catch((e) => status.textContent = e.message); });
}

async function loadModels(root) {
  try {
    const d = await api("/models");
    root.querySelector("#modelStatus").textContent = d.models_enabled
      ? `Real models on (${d.embedding_backend}, ${d.model_device}).` : "Stub mode (MW_MODELS_ENABLED=false).";
    const entries = Object.entries(d.available || {});
    root.querySelector("#models").innerHTML = entries.length
      ? entries.map(([n, ok]) => `<span class="badge ${ok ? "clean" : "warn"}">${escapeHtml(n)}: ${ok ? "on" : "off"}</span>`).join("")
      : '<span class="badge warn">no models</span>';
  } catch (_) {}
}
