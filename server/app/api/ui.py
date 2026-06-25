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
    button.linkbtn {
      background: none;
      border: 0;
      color: var(--accent);
      padding: 0 2px;
      min-height: 0;
      font-weight: 600;
      font-size: 13px;
      cursor: pointer;
      white-space: nowrap;
    }
    button.linkbtn:hover { background: none; text-decoration: underline; }
    .show-more-row td { text-align: center; }
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
    .description-cell {
      max-width: 360px;
      min-width: 220px;
      white-space: normal;
      overflow-wrap: anywhere;
      line-height: 1.35;
    }
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
    /* ---- tabs ---- */
    .tabs { display: flex; gap: 8px; border-bottom: 1px solid var(--line); }
    .tab {
      background: none; color: var(--muted); border: 0;
      border-bottom: 2px solid transparent; border-radius: 0;
      padding: 8px 14px; min-height: 0; font-weight: 700; cursor: pointer;
    }
    .tab:hover { background: none; color: var(--text); }
    .tab.active { color: var(--accent); border-bottom-color: var(--accent); }
    .tabpane { display: grid; gap: 18px; }
    /* ---- pipeline flow graph ---- */
    .flow {
      display: flex; align-items: stretch; gap: 0;
      overflow-x: auto; padding-bottom: 8px;
    }
    .stage { display: flex; align-items: stretch; }
    .stage-col {
      display: flex; flex-direction: column; gap: 10px;
      min-width: 210px; max-width: 240px;
    }
    .stage-head {
      font-size: 12px; text-transform: uppercase; letter-spacing: .04em;
      color: var(--muted); font-weight: 700; margin-bottom: 2px;
    }
    .stage-arrow {
      display: flex; align-items: center; color: var(--line);
      font-size: 24px; padding: 0 10px; user-select: none;
    }
    .node {
      border: 1px solid var(--line); border-radius: 8px; background: #fbfcff;
      padding: 10px 12px; display: grid; gap: 8px;
    }
    .node.off { opacity: 0.6; }
    .node.err { border-color: #fda29b; background: #fff4f3; }
    .node-info { background: #f3f6fb; border-style: dashed; color: var(--muted); font-size: 13px; }
    .node-title { font-weight: 700; font-size: 14px; overflow-wrap: anywhere; }
    .node-badges { display: flex; flex-wrap: wrap; gap: 5px; }
    .badge {
      font-size: 10px; text-transform: uppercase; letter-spacing: .03em;
      border-radius: 999px; padding: 2px 7px; border: 1px solid var(--line);
      background: #fff; color: var(--muted); font-weight: 700;
    }
    .badge.plugin { color: var(--accent); border-color: #b9d4f7; background: #eef5ff; }
    .node-ctl { display: flex; align-items: center; gap: 8px; font-size: 13px; color: var(--muted); }
    .node-ctl input[type=number] { width: 78px; padding: 6px 8px; }
    .node-ctl label { display: flex; align-items: center; gap: 6px; flex-direction: row; }
    .node .err-msg { color: var(--bad); font-size: 12px; overflow-wrap: anywhere; }
    .switch { display: inline-flex; align-items: center; gap: 6px; cursor: pointer; font-weight: 600; }
    .switch input { width: auto; }
    .weights-mini { font-size: 12px; color: var(--muted); line-height: 1.6; }
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
    <nav class="tabs">
      <button id="tabDashboardBtn" type="button" class="tab active" data-tab="dashboard">Dashboard</button>
      <button id="tabPipelineBtn" type="button" class="tab" data-tab="pipeline">Pipeline</button>
    </nav>

    <div id="tab-dashboard" class="tabpane">
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
      <h2>Parse Channel</h2>
      <p class="status">Point the parser-bot at an Instagram profile to record and check its reels. Requires the anti-detect browser running with CDP and a logged-in session.</p>
      <form id="parserForm">
        <label>Channel URL or handle
          <input id="channelUrl" name="channel_url" placeholder="https://www.instagram.com/username/  or  @username">
        </label>
        <div class="row">
          <label>Max reels
            <input id="maxReels" name="max_reels" type="number" min="1" placeholder="server default">
          </label>
          <div class="actions">
            <button id="startParserBtn" type="submit">Start Parsing</button>
            <button id="stopParserBtn" class="secondary" type="button">Stop</button>
          </div>
        </div>
        <div id="parserStatus" class="status">Checking parser status...</div>
      </form>
    </section>

    <section>
      <h2>Check a Reel</h2>
      <p class="status">Record and check a single reel by its link.</p>
      <form id="reelForm">
        <div class="row">
          <label>Reel URL
            <input id="reelUrl" name="reel_url" placeholder="https://www.instagram.com/reel/XXXXXXXXXXX/">
          </label>
          <button id="checkReelBtn" type="submit">Check Reel</button>
        </div>
        <div id="reelStatus" class="status"></div>
      </form>
    </section>

    <section>
      <h2>Auto-Investigate Channels</h2>
      <p class="status">When ON, if any checker scores a reel at or above its threshold, the bot automatically opens that reel's channel and scans its videos (up to the max). Set each checker's threshold (%) independently.</p>
      <div class="actions">
        <button id="autoScanBtn" type="button">Auto-scan: …</button>
      </div>
      <div class="confidence-grid">
        <label>Semantic %
          <input id="thSemantic" data-checker="semantic" type="number" min="0" max="100" step="1">
        </label>
        <label>OCR %
          <input id="thOcr" data-checker="ocr" type="number" min="0" max="100" step="1">
        </label>
        <label>CLIP %
          <input id="thClip" data-checker="clip" type="number" min="0" max="100" step="1">
        </label>
        <label>Audio %
          <input id="thAudio" data-checker="audio" type="number" min="0" max="100" step="1">
        </label>
      </div>
      <label>Max reels per channel
        <input id="autoScanMax" type="number" min="1" step="1">
      </label>
      <div id="autoScanStatus" class="status"></div>
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
      <div class="summary">
        <div class="metric"><span>Platform</span><strong id="sourcePlatform">-</strong></div>
        <div class="metric"><span>Reel</span><strong id="sourceShortcode">-</strong></div>
        <div class="metric"><span>Source URL</span><strong id="sourceUrl">-</strong></div>
        <div class="metric"><span>Description</span><strong id="sourceDescription">-</strong></div>
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
        <thead><tr><th>Reel</th><th>Description</th><th>Status</th><th>Priority</th><th>Risk</th><th>Category</th><th>Semantic</th><th>OCR</th><th>CLIP</th><th>Audio</th><th>Job</th></tr></thead>
        <tbody id="priorityList"><tr><td colspan="11">No priority data loaded.</td></tr></tbody>
      </table>
    </section>

    <section>
      <h2>Recent Reels</h2>
      <table>
        <thead><tr><th>Time</th><th>Reel</th><th>Description</th><th>Status</th><th>Semantic</th><th>OCR</th><th>CLIP</th><th>Audio</th><th>Risk</th><th>Category</th><th>Job</th></tr></thead>
        <tbody id="recentJobs"><tr><td colspan="11">No recent jobs loaded.</td></tr></tbody>
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
    </div><!-- /tab-dashboard -->

    <div id="tab-pipeline" class="tabpane" hidden>
      <section>
        <h2>Pipeline Architecture</h2>
        <p class="status">The flow each reel runs through, left to right. Toggle a checker on/off, retune its weight, set the aggregator's fraud threshold, or tune the investigator. Drop a <code>.py</code> checker in the plugins folder and press <em>Reload plugins</em> to add a new node — see <code>plugins/README.md</code> for the format.</p>
        <div class="actions">
          <button id="reloadPluginsBtn" type="button" class="secondary">Reload plugins</button>
          <span id="pluginsDir" class="status"></span>
        </div>
        <div id="archStatus" class="status"></div>
        <div id="flow" class="flow"><span class="status">Loading pipeline...</span></div>
      </section>
    </div><!-- /tab-pipeline -->
  </main>

  <script>
    const $ = (id) => document.getElementById(id);
    let pollTimer = null;

    // How many rows each list shows before "Show more"; expanded description ids.
    const PAGE_INIT = 5;
    const PAGE_STEP = 10;
    let priorityShown = PAGE_INIT;
    let recentShown = PAGE_INIT;
    let priorityItems = [];
    let recentItems = [];
    const expandedDesc = new Set();

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
      setSource(job.source || {}, job.description || "");

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

    function setSource(source, description) {
      $("sourcePlatform").textContent = source.platform || "-";
      $("sourceShortcode").textContent = source.shortcode || "-";
      $("sourceDescription").textContent = description ? description.slice(0, 80) : "-";
      if (source.url) {
        $("sourceUrl").innerHTML = `<a href="${escapeHtml(source.url)}" target="_blank" rel="noreferrer">open</a>`;
      } else {
        $("sourceUrl").textContent = "-";
      }
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
        await loadRecentJobs();
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
        await loadRecentJobs();
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
        await loadRecentJobs();
      } catch (err) {
        setStatus(err.message || String(err), true);
      } finally {
        $("clearDedupBtn").disabled = false;
      }
    });

    function renderParserStatus(s) {
      const el = $("parserStatus");
      if (s && s.running) {
        const since = s.started_at ? new Date(s.started_at * 1000).toLocaleTimeString() : "";
        el.textContent = `Running — ${s.channel} (pid ${s.pid}${since ? ", since " + since : ""}).`;
        el.className = "status warn";
        $("startParserBtn").disabled = true;
        $("stopParserBtn").disabled = false;
      } else {
        el.textContent = "Parser idle.";
        el.className = "status";
        $("startParserBtn").disabled = false;
        $("stopParserBtn").disabled = true;
      }
    }

    async function loadParserStatus() {
      try {
        const res = await fetch("/parser/status");
        if (!res.ok) return;
        renderParserStatus(await res.json());
      } catch (_) {}
    }

    $("parserForm").addEventListener("submit", async (event) => {
      event.preventDefault();
      const channel = $("channelUrl").value.trim();
      if (!channel) { $("parserStatus").textContent = "Enter a channel URL or handle."; return; }
      $("startParserBtn").disabled = true;
      try {
        const max = parseInt($("maxReels").value, 10);
        const body = { channel_url: channel };
        if (!Number.isNaN(max) && max > 0) body.max_reels = max;
        const res = await fetch("/parser/start", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        if (!res.ok) {
          const detail = await res.json().catch(() => ({}));
          throw new Error(detail.detail || (await res.text()));
        }
        renderParserStatus(await res.json());
      } catch (err) {
        $("parserStatus").textContent = err.message || String(err);
        $("parserStatus").className = "status risk";
        $("startParserBtn").disabled = false;
      }
    });

    $("stopParserBtn").addEventListener("click", async () => {
      $("stopParserBtn").disabled = true;
      try {
        const res = await fetch("/parser/stop", { method: "POST" });
        if (!res.ok) throw new Error(await res.text());
        renderParserStatus(await res.json());
        await loadRecentJobs();
      } catch (err) {
        $("parserStatus").textContent = err.message || String(err);
        $("parserStatus").className = "status risk";
        $("stopParserBtn").disabled = false;
      }
    });

    $("reelForm").addEventListener("submit", async (event) => {
      event.preventDefault();
      const url = $("reelUrl").value.trim();
      if (!url) { $("reelStatus").textContent = "Paste a reel URL."; return; }
      $("checkReelBtn").disabled = true;
      $("reelStatus").className = "status";
      $("reelStatus").textContent = "Starting reel check...";
      try {
        const res = await fetch("/parser/reel", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ reel_url: url }),
        });
        if (!res.ok) {
          const detail = await res.json().catch(() => ({}));
          throw new Error(detail.detail || (await res.text()));
        }
        $("reelStatus").textContent = "Reel check started; it will appear in Recent Reels once analyzed.";
        renderParserStatus(await res.json());
      } catch (err) {
        $("reelStatus").textContent = err.message || String(err);
        $("reelStatus").className = "status risk";
      } finally {
        $("checkReelBtn").disabled = false;
      }
    });

    let autoScan = { enabled: false, thresholds: {}, max_reels: 0 };
    const TH_INPUTS = { semantic: "thSemantic", ocr: "thOcr", clip: "thClip", audio: "thAudio" };

    function renderAutoScan() {
      const b = $("autoScanBtn");
      b.textContent = `Auto-scan: ${autoScan.enabled ? "ON" : "OFF"}`;
      b.className = autoScan.enabled ? "" : "secondary";
      const th = autoScan.thresholds || {};
      // Don't clobber a field the user is editing.
      for (const [checker, id] of Object.entries(TH_INPUTS)) {
        const el = $(id);
        if (el && document.activeElement !== el) el.value = Math.round((th[checker] ?? 0) * 100);
      }
      const maxEl = $("autoScanMax");
      if (maxEl && document.activeElement !== maxEl) maxEl.value = autoScan.max_reels || "";
    }

    async function loadAutoScan() {
      try {
        const res = await fetch("/parser/auto-scan");
        if (!res.ok) return;
        autoScan = await res.json();
        renderAutoScan();
      } catch (_) {}
    }

    async function postAutoScan(body) {
      const res = await fetch("/parser/auto-scan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(await res.text());
      autoScan = await res.json();
      renderAutoScan();
    }

    function withAutoScanError(fn) {
      return async () => {
        try {
          await fn();
          $("autoScanStatus").textContent = "Saved.";
          $("autoScanStatus").className = "status clean";
        } catch (err) {
          $("autoScanStatus").textContent = err.message || String(err);
          $("autoScanStatus").className = "status risk";
        }
      };
    }

    $("autoScanBtn").addEventListener("click", withAutoScanError(
      () => postAutoScan({ enabled: !autoScan.enabled })
    ));

    for (const [checker, id] of Object.entries(TH_INPUTS)) {
      $(id).addEventListener("change", withAutoScanError(() => {
        const pct = Math.max(0, Math.min(100, parseFloat($(id).value) || 0));
        return postAutoScan({ thresholds: { [checker]: pct / 100 } });
      }));
    }

    $("autoScanMax").addEventListener("change", withAutoScanError(() => {
      const n = parseInt($("autoScanMax").value, 10);
      return postAutoScan({ max_reels: n > 0 ? n : 1 });
    }));

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

    function descCell(item) {
      const id = item.job_id || "";
      const full = item.description || "";
      const words = full.split(/\s+/).filter(Boolean);
      if (words.length <= 10 || !id) {
        return `<td class="description-cell">${escapeHtml(full || "-")}</td>`;
      }
      const expanded = expandedDesc.has(id);
      const text = expanded ? full : words.slice(0, 10).join(" ");
      const label = expanded ? " show less" : " …more";
      return `<td class="description-cell">${escapeHtml(text)}<button type="button" class="linkbtn" data-desc="${escapeHtml(id)}">${label}</button></td>`;
    }

    function moreRow(total, shown, kind, cols) {
      let btns = "";
      if (shown < total) btns += `<button type="button" class="linkbtn" data-more="${kind}">Show more (${total - shown})</button>`;
      if (shown > PAGE_INIT) btns += ` <button type="button" class="linkbtn" data-less="${kind}">Show less</button>`;
      return btns ? `<tr class="show-more-row"><td colspan="${cols}">${btns}</td></tr>` : "";
    }

    function renderPriority() {
      const items = priorityItems;
      const rows = items.slice(0, priorityShown).map((item) => {
        const c = item.method_confidences || {};
        return `
          <tr>
            <td>${reelLink(item.source || {})}</td>
            ${descCell(item)}
            <td>${escapeHtml(item.status || "")}</td>
            <td>${formatConfidence(item.priority)}</td>
            <td>${formatConfidence(item.risk_score)}</td>
            <td>${escapeHtml(item.category || "-")}</td>
            <td>${formatConfidence(c.semantic)}</td>
            <td>${formatConfidence(c.ocr)}</td>
            <td>${formatConfidence(c.clip)}</td>
            <td>${formatConfidence(c.audio)}</td>
            <td>${escapeHtml(item.job_id || "")}</td>
          </tr>
        `;
      });
      $("priorityList").innerHTML = items.length
        ? rows.join("") + moreRow(items.length, priorityShown, "priority", 11)
        : "<tr><td colspan='11'>No jobs yet.</td></tr>";
    }

    async function loadPriorityList() {
      const res = await fetch("/priority-list");
      if (!res.ok) return;
      const data = await res.json();
      priorityItems = data.items || [];
      renderPriority();
    }

    function reelLink(source) {
      if (!source) return "-";
      const url = source.top_bar_url || source.url || source.permalink;
      const label = source.shortcode || source.platform || "open";
      return url
        ? `<a href="${escapeHtml(url)}" target="_blank" rel="noreferrer">${escapeHtml(label)}</a>`
        : escapeHtml(label || "-");
    }

    function formatTime(value) {
      if (!value) return "-";
      const date = new Date(value);
      if (Number.isNaN(date.getTime())) return escapeHtml(value);
      return date.toLocaleString();
    }

    function renderRecent() {
      const items = recentItems;
      const rows = items.slice(0, recentShown).map((item) => {
        const c = item.method_confidences || {};
        return `
          <tr>
            <td>${formatTime(item.created_at)}</td>
            <td>${reelLink(item.source || {})}</td>
            ${descCell(item)}
            <td>${escapeHtml(item.status || "")}</td>
            <td>${formatConfidence(c.semantic)}</td>
            <td>${formatConfidence(c.ocr)}</td>
            <td>${formatConfidence(c.clip)}</td>
            <td>${formatConfidence(c.audio)}</td>
            <td>${formatConfidence(item.risk_score)}</td>
            <td>${escapeHtml(item.category || "-")}</td>
            <td>${escapeHtml(item.job_id || "")}</td>
          </tr>
        `;
      });
      $("recentJobs").innerHTML = items.length
        ? rows.join("") + moreRow(items.length, recentShown, "recent", 11)
        : "<tr><td colspan='11'>No jobs yet.</td></tr>";
    }

    async function loadRecentJobs() {
      const res = await fetch("/recent-jobs");
      if (!res.ok) return;
      const data = await res.json();
      recentItems = data.items || [];
      renderRecent();
    }

    function toggleDesc(id) {
      if (expandedDesc.has(id)) expandedDesc.delete(id); else expandedDesc.add(id);
      renderPriority();
      renderRecent();
    }

    function showMore(kind) {
      if (kind === "priority") priorityShown += PAGE_STEP; else recentShown += PAGE_STEP;
      renderPriority();
      renderRecent();
    }

    function showLess(kind) {
      if (kind === "priority") priorityShown = PAGE_INIT; else recentShown = PAGE_INIT;
      renderPriority();
      renderRecent();
    }

    // ---- Pipeline tab: flow graph + live architecture editing ----
    let activeTab = "dashboard";
    let archData = null;

    function switchTab(tab) {
      activeTab = tab;
      document.querySelectorAll(".tab").forEach((b) => b.classList.toggle("active", b.dataset.tab === tab));
      $("tab-dashboard").hidden = tab !== "dashboard";
      $("tab-pipeline").hidden = tab !== "pipeline";
      if (tab === "pipeline") loadArchitecture().catch(() => {});
    }
    document.querySelectorAll(".tab").forEach((b) => b.addEventListener("click", () => switchTab(b.dataset.tab)));

    function archMsg(text, isError = false) {
      $("archStatus").textContent = text;
      $("archStatus").className = isError ? "status risk" : "status clean";
    }

    async function loadArchitecture() {
      const res = await fetch("/architecture");
      if (!res.ok) return;
      archData = await res.json();
      renderFlow();
    }

    function fmtW(v) { return typeof v === "number" ? v.toFixed(2) : "—"; }

    function pipelineNodeHtml(n) {
      if (n.error) {
        return `<div class="node err">
          <div class="node-title">${escapeHtml(n.label)}</div>
          <div class="node-badges"><span class="badge plugin">plugin</span><span class="badge">load error</span></div>
          <div class="err-msg">${escapeHtml(n.error)}</div>
        </div>`;
      }
      const weightCtl = (typeof n.weight === "number")
        ? `<div class="node-ctl"><label>weight
             <input type="number" min="0" max="1" step="0.05" value="${n.weight.toFixed(2)}" data-node-weight="${escapeHtml(n.id)}"></label></div>`
        : "";
      const del = n.removable
        ? `<div class="node-ctl"><button type="button" class="linkbtn" data-node-del="${escapeHtml(n.id)}">remove</button></div>`
        : "";
      return `<div class="node${n.enabled ? "" : " off"}">
        <div class="node-title">${escapeHtml(n.label)}</div>
        <div class="node-badges">
          <span class="badge ${n.source === "plugin" ? "plugin" : ""}">${escapeHtml(n.source)}</span>
          ${n.checker ? `<span class="badge">${escapeHtml(n.checker)}</span>` : ""}
        </div>
        <label class="switch"><input type="checkbox" data-node-toggle="${escapeHtml(n.id)}" ${n.enabled ? "checked" : ""}> ${n.enabled ? "enabled" : "disabled"}</label>
        ${weightCtl}${del}
      </div>`;
    }

    function aggregateNodeHtml(n) {
      const rows = Object.entries(n.weights || {}).map(([k, v]) => `${escapeHtml(k)}: ${fmtW(v)}`).join("<br>");
      return `<div class="node">
        <div class="node-title">Aggregator</div>
        <div class="node-badges"><span class="badge">weighted sum</span></div>
        <div class="node-ctl"><label>fraud ≥
          <input type="number" min="0" max="1" step="0.05" value="${(n.category_threshold ?? 0).toFixed(2)}" data-agg-threshold></label></div>
        <div class="weights-mini">${rows}</div>
      </div>`;
    }

    function investigateNodeHtml(n) {
      const th = n.thresholds || {};
      const row = (label, key) => `<div class="node-ctl"><label>${label} %
        <input type="number" min="0" max="100" step="1" value="${Math.round((th[key] ?? 0) * 100)}" data-inv-th="${key}"></label></div>`;
      return `<div class="node${n.enabled ? "" : " off"}">
        <div class="node-title">Investigator</div>
        <div class="node-badges"><span class="badge">auto-scan</span></div>
        <label class="switch"><input type="checkbox" data-inv-toggle ${n.enabled ? "checked" : ""}> ${n.enabled ? "ON" : "OFF"}</label>
        <div class="node-ctl"><label>max reels <input type="number" min="1" step="1" value="${n.max_reels || ""}" data-inv-max></label></div>
        ${row("Semantic", "semantic")}${row("OCR", "ocr")}${row("CLIP", "clip")}${row("Audio", "audio")}
      </div>`;
    }

    function stageColHtml(stage) {
      let body = "";
      if (stage.kind === "info") body = `<div class="node node-info">${escapeHtml(stage.note || "")}</div>`;
      else if (stage.kind === "pipelines") body = (stage.nodes || []).map(pipelineNodeHtml).join("") || `<div class="node node-info">none</div>`;
      else if (stage.kind === "aggregate") body = aggregateNodeHtml((stage.nodes || [])[0] || {});
      else if (stage.kind === "investigate") body = investigateNodeHtml((stage.nodes || [])[0] || {});
      return `<div class="stage"><div class="stage-col"><div class="stage-head">${escapeHtml(stage.label)}</div>${body}</div></div>`;
    }

    function renderFlow() {
      if (!archData) return;
      $("flow").innerHTML = archData.stages.map(stageColHtml).join('<div class="stage-arrow">&rsaquo;</div>');
      $("pluginsDir").textContent = archData.plugins_dir ? `plugins folder: ${archData.plugins_dir}` : "";
    }

    async function postNode(id, body) {
      const res = await fetch(`/architecture/node/${encodeURIComponent(id)}`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(await res.text());
    }

    async function deleteNode(id) {
      if (!confirm(`Remove checker "${id}" from the running pipeline? (the plugin file stays on disk)`)) return;
      try {
        const res = await fetch(`/architecture/node/${encodeURIComponent(id)}`, { method: "DELETE" });
        if (!res.ok) throw new Error(await res.text());
        await loadArchitecture();
        archMsg(`Removed ${id}.`);
      } catch (err) { archMsg(err.message || String(err), true); }
    }

    $("reloadPluginsBtn").addEventListener("click", async () => {
      $("reloadPluginsBtn").disabled = true;
      try {
        const res = await fetch("/architecture/reload", { method: "POST" });
        if (!res.ok) throw new Error(await res.text());
        archData = await res.json();
        renderFlow();
        archMsg("Plugins reloaded.");
      } catch (err) { archMsg(err.message || String(err), true); }
      finally { $("reloadPluginsBtn").disabled = false; }
    });

    document.addEventListener("change", async (e) => {
      const d = e.target && e.target.dataset;
      if (!d) return;
      try {
        if (d.nodeToggle !== undefined) { await postNode(d.nodeToggle, { enabled: e.target.checked }); await loadArchitecture(); archMsg("Saved."); }
        else if (d.nodeWeight !== undefined) { await postNode(d.nodeWeight, { weight: parseFloat(e.target.value) || 0 }); await loadArchitecture(); archMsg("Saved."); }
        else if (d.aggThreshold !== undefined) {
          const r = await fetch("/architecture/aggregate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ category_threshold: parseFloat(e.target.value) || 0 }) });
          if (!r.ok) throw new Error(await r.text());
          await loadArchitecture(); archMsg("Saved.");
        }
        else if (d.invToggle !== undefined) { await postAutoScan({ enabled: e.target.checked }); await loadArchitecture(); archMsg("Saved."); }
        else if (d.invMax !== undefined) { const n = parseInt(e.target.value, 10); await postAutoScan({ max_reels: n > 0 ? n : 1 }); await loadArchitecture(); archMsg("Saved."); }
        else if (d.invTh !== undefined) { const pct = Math.max(0, Math.min(100, parseFloat(e.target.value) || 0)); await postAutoScan({ thresholds: { [d.invTh]: pct / 100 } }); await loadArchitecture(); archMsg("Saved."); }
      } catch (err) { archMsg(err.message || String(err), true); }
    });

    document.addEventListener("click", (e) => {
      const d = e.target && e.target.dataset;
      if (!d) return;
      if (d.desc) toggleDesc(d.desc);
      else if (d.more) showMore(d.more);
      else if (d.less) showLess(d.less);
      else if (d.nodeDel) deleteNode(d.nodeDel);
    });

    switchTab("dashboard");
    loadModels().catch(() => {});
    loadPriorityList().catch(() => {});
    loadRecentJobs().catch(() => {});
    loadParserStatus().catch(() => {});
    loadAutoScan().catch(() => {});
    setInterval(() => {
      if (activeTab !== "dashboard") return;  // don't clobber pipeline edits
      loadPriorityList().catch(() => {});
      loadRecentJobs().catch(() => {});
      loadModels().catch(() => {});
      loadParserStatus().catch(() => {});
      loadAutoScan().catch(() => {});
    }, 3000);
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
