from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse

from app.api.deps import get_components

router = APIRouter()


PAGE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AI Media Watch</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f5f7fb;
      --panel: #ffffff;
      --text: #172033;
      --muted: #667085;
      --line: #d9dee8;
      --accent: #1769e0;
      --accent-strong: #0f4fb0;
      --bad: #b42318;
      --good: #067647;
      --warn: #b54708;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--text);
    }
    header {
      padding: 24px clamp(16px, 4vw, 48px) 16px;
      border-bottom: 1px solid var(--line);
      background: #fff;
    }
    h1 { margin: 0; font-size: 24px; line-height: 1.2; font-weight: 700; }
    main {
      width: min(1120px, calc(100% - 32px));
      margin: 24px auto 48px;
      display: grid;
      gap: 18px;
    }
    section {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 18px;
    }
    h2 { margin: 0 0 14px; font-size: 16px; }
    form { display: grid; gap: 12px; }
    label { display: grid; gap: 6px; color: var(--muted); font-size: 13px; font-weight: 600; }
    input, textarea, button {
      font: inherit;
      border-radius: 6px;
    }
    input, textarea {
      width: 100%;
      border: 1px solid var(--line);
      padding: 10px 12px;
      background: #fff;
      color: var(--text);
    }
    textarea { min-height: 100px; resize: vertical; }
    .row {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 10px;
      align-items: end;
    }
    button {
      border: 0;
      background: var(--accent);
      color: #fff;
      padding: 10px 14px;
      min-height: 40px;
      cursor: pointer;
      font-weight: 700;
      white-space: nowrap;
    }
    button:hover { background: var(--accent-strong); }
    button:disabled { opacity: 0.55; cursor: wait; }
    button.secondary {
      background: #eef2f7;
      color: var(--text);
      border: 1px solid var(--line);
    }
    button.secondary:hover { background: #e4e9f2; }
    .actions {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }
    .status {
      min-height: 24px;
      color: var(--muted);
      font-size: 14px;
    }
    .summary {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
      margin-bottom: 14px;
    }
    .confidence-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
      margin: 0 0 14px;
    }
    .metric {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      background: #fbfcff;
      min-height: 72px;
    }
    .metric span { display: block; color: var(--muted); font-size: 12px; margin-bottom: 6px; }
    .metric strong { display: block; font-size: 18px; overflow-wrap: anywhere; }
    .clean { color: var(--good); }
    .risk { color: var(--bad); }
    .warn { color: var(--warn); }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
    }
    th, td {
      border-bottom: 1px solid var(--line);
      padding: 10px 8px;
      text-align: left;
      vertical-align: top;
    }
    th { color: var(--muted); font-size: 12px; text-transform: uppercase; }
    pre {
      margin: 0;
      padding: 12px;
      border-radius: 8px;
      background: #101828;
      color: #f2f4f7;
      overflow: auto;
      max-height: 320px;
      font-size: 12px;
      line-height: 1.45;
    }
    .models {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 8px;
    }
    .pill {
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 5px 9px;
      background: #fff;
      font-size: 12px;
      color: var(--muted);
    }
    .pill.on { color: var(--good); border-color: #abefc6; background: #ecfdf3; }
    .pill.off { color: var(--warn); border-color: #fedf89; background: #fffaeb; }
    @media (max-width: 760px) {
      .summary, .confidence-grid { grid-template-columns: 1fr 1fr; }
      .row { grid-template-columns: 1fr; }
      button { width: 100%; }
    }
  </style>
</head>
<body>
  <header>
    <h1>AI Media Watch</h1>
  </header>
  <main>
    <section>
      <h2>Upload Video</h2>
      <form id="uploadForm">
        <label>Video file
          <input id="video" name="video" type="file" accept="video/*" required>
        </label>
        <label>Description
          <textarea id="description" name="description" required placeholder="Paste caption or describe what is shown in the reel"></textarea>
        </label>
        <div class="actions">
          <button id="uploadBtn" type="submit">Upload and Check</button>
          <button id="clearDedupBtn" class="secondary" type="button">Clear Dedup</button>
        </div>
        <div id="uploadStatus" class="status"></div>
      </form>
    </section>

    <section>
      <h2>Find Existing Result</h2>
      <div class="row">
        <label>Job ID
          <input id="jobIdInput" placeholder="Paste job_id">
        </label>
        <button id="loadJobBtn" type="button">Load Result</button>
      </div>
    </section>

    <section>
      <h2>Result</h2>
      <div class="summary">
        <div class="metric"><span>Job</span><strong id="jobId">-</strong></div>
        <div class="metric"><span>Status</span><strong id="jobStatus">-</strong></div>
        <div class="metric"><span>Risk</span><strong id="riskScore">-</strong></div>
        <div class="metric"><span>Category</span><strong id="category">-</strong></div>
      </div>
      <div class="confidence-grid">
        <div class="metric"><span>Semantic</span><strong id="semanticConfidence">-</strong></div>
        <div class="metric"><span>OCR</span><strong id="ocrConfidence">-</strong></div>
        <div class="metric"><span>CLIP</span><strong id="clipConfidence">-</strong></div>
        <div class="metric"><span>Audio</span><strong id="audioConfidence">-</strong></div>
      </div>
      <table>
        <thead><tr><th>Modality</th><th>Signal</th><th>Confidence</th><th>Evidence</th></tr></thead>
        <tbody id="findings"><tr><td colspan="4">No result loaded.</td></tr></tbody>
      </table>
    </section>

    <section>
      <h2>Priority List</h2>
      <table>
        <thead><tr><th>Job</th><th>Status</th><th>Priority</th><th>Risk</th><th>Semantic</th><th>OCR</th><th>CLIP</th><th>Audio</th></tr></thead>
        <tbody id="priorityList"><tr><td colspan="8">No priority data loaded.</td></tr></tbody>
      </table>
    </section>

    <section>
      <h2>Explanations</h2>
      <pre id="explanations">No explanations loaded.</pre>
    </section>

    <section>
      <h2>Loaded Models</h2>
      <div id="modelStatus" class="status">Loading model status...</div>
      <div id="models" class="models"></div>
    </section>
  </main>

  <script>
    const $ = (id) => document.getElementById(id);
    let pollTimer = null;

    function setStatus(message, isError = false) {
      $("uploadStatus").textContent = message;
      $("uploadStatus").className = isError ? "status risk" : "status";
    }

    function setResult(job) {
      $("jobId").textContent = job.job_id || "-";
      $("jobStatus").textContent = job.status || "-";
      $("riskScore").textContent = typeof job.risk_score === "number" ? job.risk_score.toFixed(3) : "-";
      $("category").textContent = job.category || "-";
      $("category").className = job.category && job.category !== "clean" ? "risk" : "clean";
      setConfidenceMetrics(job.method_confidences || {});

      const rows = (job.findings || []).map((f) => `
        <tr>
          <td>${escapeHtml(f.modality || "")}</td>
          <td>${escapeHtml(f.signal_type || "")}</td>
          <td>${typeof f.confidence === "number" ? f.confidence.toFixed(3) : ""}</td>
          <td><pre>${escapeHtml(JSON.stringify(f.evidence || {}, null, 2))}</pre></td>
        </tr>
      `);
      $("findings").innerHTML = rows.length ? rows.join("") : "<tr><td colspan='4'>No findings.</td></tr>";
    }

    function formatConfidence(value) {
      return typeof value === "number" ? value.toFixed(3) : "-";
    }

    function setConfidenceMetrics(conf) {
      $("semanticConfidence").textContent = formatConfidence(conf.semantic);
      $("ocrConfidence").textContent = formatConfidence(conf.ocr);
      $("clipConfidence").textContent = formatConfidence(conf.clip);
      $("audioConfidence").textContent = formatConfidence(conf.audio);
    }

    function escapeHtml(value) {
      return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }

    async function loadJob(jobId, poll = false) {
      const res = await fetch(`/jobs/${encodeURIComponent(jobId)}`);
      if (!res.ok) throw new Error(await res.text());
      const job = await res.json();
      setResult(job);
      $("jobIdInput").value = job.job_id;

      if (job.status === "done" || job.status === "failed") {
        if (pollTimer) clearInterval(pollTimer);
        pollTimer = null;
        await loadExplanations(job.job_id);
        await loadPriorityList();
        setStatus(job.status === "done" ? "Analysis complete." : "Analysis failed.", job.status === "failed");
      } else if (poll) {
        setStatus(`Job ${job.status}; waiting for analysis...`);
      }
      return job;
    }

    async function loadExplanations(jobId) {
      const res = await fetch(`/jobs/${encodeURIComponent(jobId)}/explanations`);
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      $("explanations").textContent = JSON.stringify(data.explanations || [], null, 2);
    }

    function pollJob(jobId) {
      if (pollTimer) clearInterval(pollTimer);
      pollTimer = setInterval(() => {
        loadJob(jobId, true).catch((err) => setStatus(err.message, true));
      }, 1000);
      return loadJob(jobId, true);
    }

    $("uploadForm").addEventListener("submit", async (event) => {
      event.preventDefault();
      $("uploadBtn").disabled = true;
      try {
        setStatus("Uploading...");
        const formData = new FormData();
        formData.append("video", $("video").files[0]);
        formData.append("description", $("description").value);
        formData.append("source_platform", "manual-ui");
        const res = await fetch("/videos", { method: "POST", body: formData });
        if (!res.ok) throw new Error(await res.text());
        const data = await res.json();
        setStatus(data.duplicate ? "Duplicate video; loading existing result..." : "Uploaded; waiting for analysis...");
        await pollJob(data.job_id);
      } catch (err) {
        setStatus(err.message || String(err), true);
      } finally {
        $("uploadBtn").disabled = false;
      }
    });

    $("loadJobBtn").addEventListener("click", async () => {
      const jobId = $("jobIdInput").value.trim();
      if (!jobId) return;
      try {
        setStatus("Loading result...");
        await loadJob(jobId);
        await loadPriorityList();
        setStatus("Result loaded.");
      } catch (err) {
        setStatus(err.message || String(err), true);
      }
    });

    $("clearDedupBtn").addEventListener("click", async () => {
      if (!confirm("Clear exact-video dedup hashes? Existing jobs will stay.")) return;
      $("clearDedupBtn").disabled = true;
      try {
        setStatus("Clearing dedup...");
        const res = await fetch("/dedup/clear", { method: "POST" });
        if (!res.ok) throw new Error(await res.text());
        const data = await res.json();
        setStatus(`Dedup cleared for ${data.cleared} job(s).`);
        await loadPriorityList();
      } catch (err) {
        setStatus(err.message || String(err), true);
      } finally {
        $("clearDedupBtn").disabled = false;
      }
    });

    async function loadModels() {
      const res = await fetch("/models");
      if (!res.ok) return;
      const data = await res.json();
      const devices = data.devices || {};
      const deviceText = devices.requested
        ? `requested: ${devices.requested}, torch: ${devices.torch}, whisper: ${devices.whisper}`
        : `requested: ${data.model_device}`;
      $("modelStatus").textContent = data.models_enabled
        ? `Real model mode is enabled. OCR embedding backend: ${data.embedding_backend}. Devices: ${deviceText}.`
        : "Stub mode is active. Set MW_MODELS_ENABLED=true to load real models at startup.";
      const entries = Object.entries(data.available || {});
      $("models").innerHTML = entries.length
        ? entries.map(([name, ready]) => `<span class="pill ${ready ? "on" : "off"}">${escapeHtml(name)}: ${ready ? "loaded" : "off"}</span>`).join("")
        : "<span class='pill off'>no model object</span>";
    }

    async function loadPriorityList() {
      const res = await fetch("/priority-list");
      if (!res.ok) return;
      const data = await res.json();
      const rows = (data.items || []).map((item) => {
        const c = item.method_confidences || {};
        return `
          <tr>
            <td>${escapeHtml(item.job_id || "")}</td>
            <td>${escapeHtml(item.status || "")}</td>
            <td>${formatConfidence(item.priority)}</td>
            <td>${formatConfidence(item.risk_score)}</td>
            <td>${formatConfidence(c.semantic)}</td>
            <td>${formatConfidence(c.ocr)}</td>
            <td>${formatConfidence(c.clip)}</td>
            <td>${formatConfidence(c.audio)}</td>
          </tr>
        `;
      });
      $("priorityList").innerHTML = rows.length ? rows.join("") : "<tr><td colspan='8'>No jobs yet.</td></tr>";
    }

    loadModels().catch(() => {});
    loadPriorityList().catch(() => {});
  </script>
</body>
</html>
"""


@router.get("/", response_class=HTMLResponse)
async def index() -> str:
    return PAGE


@router.get("/models")
async def models(components=Depends(get_components)) -> dict:
    loaded = components.models.available() if components.models is not None else {}
    return {
        "models_enabled": components.settings.models_enabled,
        "model_device": components.settings.model_device,
        "devices": components.models.devices() if components.models is not None else {},
        "allow_model_downloads": components.settings.allow_model_downloads,
        "embedding_backend": components.settings.embedding_backend,
        "available": loaded,
    }
