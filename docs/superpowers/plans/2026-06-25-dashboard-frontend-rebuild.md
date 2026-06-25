# Dashboard Frontend Rebuild — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the monolithic embedded HTML dashboard with a static-file, multi-view operator console (served from the main FastAPI server on :8000) that surfaces Jobs, Job Detail, readable findings, OSINT, an investigation graph, the pipeline editor, and controls.

**Architecture:** The frontend becomes vanilla-JS ES modules + CSS under `server/app/static/`, mounted via `StaticFiles`; `GET /` returns `index.html`. The browser only talks to the main server: new proxy endpoints (`/osint/*`, `/telegram/*`) forward to the investigator/telegram services and degrade gracefully when they are offline, and a new `GET /jobs/{id}/video` streams the buffered file.

**Tech Stack:** FastAPI, `httpx` (already a dependency via parser/investigator stack — verify), `pytest` + `pytest-asyncio`, vanilla JS ES modules, `cytoscape.js` (CDN).

## Global Constraints

- No React / Vite / build step. Frontend is hand-written static files.
- All `/osint/*` and `/telegram/*` handlers must return HTTP 200 with
  `{"available": false, "reason": <str>}` on upstream connection error/timeout —
  never propagate a 5xx to the browser.
- Config setting prefix is `MW_` (pydantic-settings `env_prefix="MW_"`).
- Risk color tokens: green = `clean`, amber = `warn`, red = `scam`.
- Keep all existing endpoints and their response shapes unchanged.
- Python: `from __future__ import annotations` at top of new modules, matching
  the codebase style.

---

## File Structure

**Backend (create/modify):**
- Modify `server/app/config.py` — add `investigator_url`, `telegram_url`, `httpx_timeout_seconds`.
- Create `server/app/api/investigation.py` — `/osint/*`, `/telegram/*` proxy router.
- Modify `server/app/api/jobs.py` — add `GET /jobs/{job_id}/video`.
- Modify `server/app/api/ui.py` — `index()` returns the static `index.html`; drop `PAGE`/`ARCHITECTURE_PAGE`; keep `/models`; redirect `/architecture-ui`.
- Modify `server/app/main.py` — mount `StaticFiles`, include `investigation` router.
- Create `server/tests/test_investigation_proxy.py`, `server/tests/test_job_video.py`.

**Frontend (create under `server/app/static/`):**
- `index.html`, `styles.css`
- `js/api.js`, `js/router.js`, `js/app.js`, `js/util.js`
- `js/components/riskBadge.js`, `js/components/findings.js`, `js/components/graph.js`
- `js/views/overview.js`, `js/views/jobs.js`, `js/views/jobDetail.js`, `js/views/investigation.js`, `js/views/pipeline.js`, `js/views/controls.js`

---

## Task 1: Backend config additions

**Files:**
- Modify: `server/app/config.py:57` (after the auto_scan thresholds block)
- Test: `server/tests/test_config_investigation.py`

**Interfaces:**
- Produces: `Settings.investigator_url: str` (default `http://localhost:8010`),
  `Settings.telegram_url: str` (default `http://localhost:8020`),
  `Settings.httpx_timeout_seconds: float` (default `5.0`).

- [ ] **Step 1: Write the failing test**

```python
# server/tests/test_config_investigation.py
from __future__ import annotations

from app.config import Settings


def test_investigation_defaults():
    s = Settings()
    assert s.investigator_url == "http://localhost:8010"
    assert s.telegram_url == "http://localhost:8020"
    assert s.httpx_timeout_seconds == 5.0


def test_investigation_env_override(monkeypatch):
    monkeypatch.setenv("MW_INVESTIGATOR_URL", "http://inv:9000")
    s = Settings()
    assert s.investigator_url == "http://inv:9000"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd server && python -m pytest tests/test_config_investigation.py -v`
Expected: FAIL — `AttributeError: 'Settings' object has no attribute 'investigator_url'`

- [ ] **Step 3: Add the settings**

In `server/app/config.py`, immediately after line 57 (the
`auto_scan_threshold_audio` field) and before the `enabled_pipeline_list`
property, add:

```python
    # External OSINT services the dashboard proxies to. Each call degrades
    # gracefully (returns {"available": false}) when the service is unreachable.
    investigator_url: str = "http://localhost:8010"
    telegram_url: str = "http://localhost:8020"
    httpx_timeout_seconds: float = 5.0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd server && python -m pytest tests/test_config_investigation.py -v`
Expected: PASS (both tests)

- [ ] **Step 5: Commit**

```bash
git add server/app/config.py server/tests/test_config_investigation.py
git commit -m "Add investigator/telegram URL settings"
```

---

## Task 2: OSINT/Telegram proxy router

**Files:**
- Create: `server/app/api/investigation.py`
- Test: `server/tests/test_investigation_proxy.py`

**Interfaces:**
- Consumes: `Settings.investigator_url`, `Settings.telegram_url`,
  `Settings.httpx_timeout_seconds` (Task 1); `get_components` from
  `app.api.deps` (returns `Components` with `.settings`).
- Produces: `router` (APIRouter) with:
  - `GET /osint/graph` (query `min_shared: int = 2`)
  - `GET /osint/accounts/{job_id}`
  - `POST /osint/accounts` (body `{"usernames": [str]}`)
  - `GET /telegram/channels` (query `sort: str = "risk"`)
  - `GET /telegram/channels/{username}`
  - Helper `async def _proxy(method, url, *, timeout, json=None, params=None) -> dict`
    returning `{"available": True, **payload}` or `{"available": False, "reason": str}`.

- [ ] **Step 1: Write the failing test**

```python
# server/tests/test_investigation_proxy.py
from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api import investigation
from app.config import Settings


def _app(monkeypatch, handler):
    """Build an app whose proxy uses a mock httpx transport calling `handler`."""
    app = FastAPI()
    app.include_router(investigation.router)

    class _Comp:
        settings = Settings()

    app.state.components = _Comp()

    real_async_client = httpx.AsyncClient

    def fake_client(*args, **kwargs):
        kwargs.pop("timeout", None)
        return real_async_client(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(investigation.httpx, "AsyncClient", fake_client)
    return app


@pytest.mark.asyncio
async def test_graph_passthrough(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/graph"
        return httpx.Response(200, json={"nodes": [{"id": "account:x"}], "edges": []})

    app = _app(monkeypatch, handler)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/osint/graph?min_shared=3")
    assert r.status_code == 200
    body = r.json()
    assert body["available"] is True
    assert body["nodes"] == [{"id": "account:x"}]


@pytest.mark.asyncio
async def test_graph_offline_returns_available_false(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    app = _app(monkeypatch, handler)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/osint/graph")
    assert r.status_code == 200
    body = r.json()
    assert body["available"] is False
    assert "reason" in body


@pytest.mark.asyncio
async def test_post_accounts_forwards_body(monkeypatch):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["json"] = request.read().decode()
        return httpx.Response(200, json={"job_id": "j1", "accepted": 2})

    app = _app(monkeypatch, handler)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/osint/accounts", json={"usernames": ["a", "b"]})
    assert r.json()["available"] is True
    assert r.json()["job_id"] == "j1"
    assert "usernames" in seen["json"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd server && python -m pytest tests/test_investigation_proxy.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.api.investigation'`

- [ ] **Step 3: Implement the router**

```python
# server/app/api/investigation.py
from __future__ import annotations

import httpx
from fastapi import APIRouter, Body, Depends

from app.api.deps import get_components

router = APIRouter()


async def _proxy(
    method: str,
    url: str,
    *,
    timeout: float,
    json: dict | None = None,
    params: dict | None = None,
) -> dict:
    """Forward a request to an external OSINT service.

    Returns the upstream JSON merged with ``available: True``. On any connection
    or timeout error (service down), returns ``{"available": False, "reason": ...}``
    so the browser shows an offline banner instead of an error page.
    """
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.request(method, url, json=json, params=params)
            resp.raise_for_status()
            payload = resp.json()
    except (httpx.HTTPError, ValueError) as exc:  # ValueError: bad JSON
        return {"available": False, "reason": str(exc)}
    if isinstance(payload, list):
        return {"available": True, "items": payload}
    return {"available": True, **payload}


@router.get("/osint/graph")
async def osint_graph(min_shared: int = 2, components=Depends(get_components)) -> dict:
    s = components.settings
    return await _proxy(
        "GET",
        f"{s.investigator_url.rstrip('/')}/graph",
        timeout=s.httpx_timeout_seconds,
        params={"min_shared": min_shared},
    )


@router.get("/osint/accounts/{job_id}")
async def osint_account_job(job_id: str, components=Depends(get_components)) -> dict:
    s = components.settings
    return await _proxy(
        "GET",
        f"{s.investigator_url.rstrip('/')}/accounts/{job_id}",
        timeout=s.httpx_timeout_seconds,
    )


@router.post("/osint/accounts")
async def osint_accounts(
    body: dict = Body(...), components=Depends(get_components)
) -> dict:
    s = components.settings
    return await _proxy(
        "POST",
        f"{s.investigator_url.rstrip('/')}/accounts",
        timeout=s.httpx_timeout_seconds,
        json=body,
    )


@router.get("/telegram/channels")
async def telegram_channels(sort: str = "risk", components=Depends(get_components)) -> dict:
    s = components.settings
    return await _proxy(
        "GET",
        f"{s.telegram_url.rstrip('/')}/channels",
        timeout=s.httpx_timeout_seconds,
        params={"sort": sort},
    )


@router.get("/telegram/channels/{username}")
async def telegram_channel(username: str, components=Depends(get_components)) -> dict:
    s = components.settings
    return await _proxy(
        "GET",
        f"{s.telegram_url.rstrip('/')}/channels/{username}",
        timeout=s.httpx_timeout_seconds,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd server && python -m pytest tests/test_investigation_proxy.py -v`
Expected: PASS (3 tests). If `httpx` is missing, run `pip install httpx` and add
it to `server/pyproject.toml` dependencies, then commit that too.

- [ ] **Step 5: Wire the router into the app**

In `server/app/main.py` line 9, add `investigation` to the import:

```python
from app.api import architecture, dedup, health, investigation, jobs, parser, pipelines, review, ui, videos
```

In `server/app/main.py` line 143, add `investigation` to the include loop:

```python
    for module in (ui, health, videos, jobs, review, pipelines, dedup, parser, architecture, investigation):
        app.include_router(module.router)
```

- [ ] **Step 6: Commit**

```bash
git add server/app/api/investigation.py server/app/main.py server/tests/test_investigation_proxy.py
git commit -m "Add OSINT/telegram proxy router with graceful degradation"
```

---

## Task 3: Video streaming endpoint

**Files:**
- Modify: `server/app/api/jobs.py`
- Test: `server/tests/test_job_video.py`

**Interfaces:**
- Consumes: `components.repo.get_job(job_id)` -> job with `.buffer_path: str | None`.
- Produces: `GET /jobs/{job_id}/video` -> `FileResponse` (200) when the file
  exists on disk; `404` when the job/file is missing.

- [ ] **Step 1: Write the failing test**

```python
# server/tests/test_job_video.py
from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api import jobs


class _Repo:
    def __init__(self, job):
        self._job = job

    async def get_job(self, job_id):
        return self._job


class _Job:
    def __init__(self, buffer_path):
        self.buffer_path = buffer_path


def _app(job):
    app = FastAPI()
    app.include_router(jobs.router)

    class _Comp:
        repo = _Repo(job)

    app.state.components = _Comp()
    return app


@pytest.mark.asyncio
async def test_video_served_when_present(tmp_path):
    f = tmp_path / "v.mp4"
    f.write_bytes(b"\x00\x01\x02fakevideo")
    app = _app(_Job(str(f)))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/jobs/abc/video")
    assert r.status_code == 200
    assert r.content == b"\x00\x01\x02fakevideo"


@pytest.mark.asyncio
async def test_video_404_when_missing(tmp_path):
    app = _app(_Job(str(tmp_path / "nope.mp4")))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/jobs/abc/video")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_video_404_when_no_job():
    app = _app(None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/jobs/abc/video")
    assert r.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd server && python -m pytest tests/test_job_video.py -v`
Expected: FAIL — 404 for the "present" test (route not defined yet).

- [ ] **Step 3: Implement the endpoint**

In `server/app/api/jobs.py`, update the imports at the top:

```python
import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
```

Append at the end of `server/app/api/jobs.py`:

```python
@router.get("/jobs/{job_id}/video")
async def get_job_video(job_id: str, components=Depends(get_components)):
    job = await components.repo.get_job(job_id)
    if job is None or not job.buffer_path or not os.path.isfile(job.buffer_path):
        raise HTTPException(status_code=404, detail="video not available")
    return FileResponse(job.buffer_path)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd server && python -m pytest tests/test_job_video.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add server/app/api/jobs.py server/tests/test_job_video.py
git commit -m "Add GET /jobs/{id}/video streaming endpoint"
```

---

## Task 4: Static mount + app shell (sidebar, router, empty views)

This task makes `/` serve a new static page with working sidebar navigation and
empty view panes. Existing endpoints keep working; views are filled in later
tasks. After this task the old `PAGE`/`ARCHITECTURE_PAGE` strings are gone.

**Files:**
- Create: `server/app/static/index.html`
- Create: `server/app/static/styles.css`
- Create: `server/app/static/js/util.js`
- Create: `server/app/static/js/api.js`
- Create: `server/app/static/js/router.js`
- Create: `server/app/static/js/app.js`
- Create empty stub view modules (filled later): `server/app/static/js/views/overview.js`, `jobs.js`, `jobDetail.js`, `investigation.js`, `pipeline.js`, `controls.js`
- Modify: `server/app/main.py` (mount static)
- Modify: `server/app/api/ui.py` (serve index.html, drop PAGE strings, keep `/models`, redirect `/architecture-ui`)

**Interfaces:**
- Produces:
  - `api.js`: `export async function api(path, opts)` (returns parsed JSON, throws `Error` with server text on non-OK), `export function fmt(n)` (3-dp or `-`).
  - `util.js`: `export const $ = (sel, root=document) => root.querySelector(sel)`, `export const el = (tag, attrs, ...children) => HTMLElement`, `export function escapeHtml(s)`.
  - `router.js`: `export function startRouter(routes, mount)` where `routes` is `{ name: { match: RegExp, render: (params, mount) => void } }`; parses `location.hash` (`#/overview`, `#/jobs`, `#/jobs/:id`).
  - Each view module exports `export function render(mount, params)` and optionally `export function stop()` (clears its polling timers).

- [ ] **Step 1: Create `util.js`**

```javascript
// server/app/static/js/util.js
export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

export function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;").replaceAll("'", "&#039;");
}

export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (k === "class") node.className = v;
    else if (k === "html") node.innerHTML = v;
    else if (k.startsWith("on") && typeof v === "function") node.addEventListener(k.slice(2), v);
    else if (v !== null && v !== undefined) node.setAttribute(k, v);
  }
  for (const c of children.flat()) {
    if (c === null || c === undefined) continue;
    node.append(c.nodeType ? c : document.createTextNode(String(c)));
  }
  return node;
}

export function fmtTime(value) {
  if (!value) return "-";
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? String(value) : d.toLocaleString();
}
```

- [ ] **Step 2: Create `api.js`**

```javascript
// server/app/static/js/api.js
export async function api(path, opts = {}) {
  const res = await fetch(path, opts);
  if (!res.ok) throw new Error((await res.text()) || res.statusText);
  const ct = res.headers.get("content-type") || "";
  return ct.includes("application/json") ? res.json() : res.text();
}

export async function postJson(path, body) {
  return api(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
}

export function fmt(n) {
  return typeof n === "number" ? n.toFixed(3) : "-";
}
```

- [ ] **Step 3: Create `router.js`**

```javascript
// server/app/static/js/router.js
let current = null;

export function startRouter(routes, mount) {
  async function handle() {
    const hash = location.hash.replace(/^#/, "") || "/overview";
    if (current && current.stop) { try { current.stop(); } catch (_) {} }
    mount.innerHTML = "";
    for (const route of routes) {
      const m = hash.match(route.match);
      if (m) {
        current = route.module;
        document.querySelectorAll("[data-nav]").forEach((a) =>
          a.classList.toggle("active", a.dataset.nav === route.nav));
        await route.module.render(mount, m.slice(1));
        return;
      }
    }
    mount.textContent = "Not found";
  }
  window.addEventListener("hashchange", handle);
  handle();
}
```

- [ ] **Step 4: Create the stub view modules**

Create each of these six files with this exact stub (replace `NAME`):

```javascript
// server/app/static/js/views/overview.js  (repeat for jobs, jobDetail, investigation, pipeline, controls)
export function render(mount) {
  mount.innerHTML = '<section class="card"><h2>overview</h2><p class="muted">Coming up.</p></section>';
}
export function stop() {}
```

For `jobDetail.js`, `jobs.js` etc. use the matching title text. These are
replaced in Tasks 5-10.

- [ ] **Step 5: Create `app.js`**

```javascript
// server/app/static/js/app.js
import { startRouter } from "./router.js";
import * as overview from "./views/overview.js";
import * as jobs from "./views/jobs.js";
import * as jobDetail from "./views/jobDetail.js";
import * as investigation from "./views/investigation.js";
import * as pipeline from "./views/pipeline.js";
import * as controls from "./views/controls.js";

const routes = [
  { match: /^\/overview$/, nav: "overview", module: overview },
  { match: /^\/jobs\/([^/]+)$/, nav: "jobs", module: jobDetail },
  { match: /^\/jobs$/, nav: "jobs", module: jobs },
  { match: /^\/investigation$/, nav: "investigation", module: investigation },
  { match: /^\/pipeline$/, nav: "pipeline", module: pipeline },
  { match: /^\/controls$/, nav: "controls", module: controls },
];

startRouter(routes, document.getElementById("view"));
```

- [ ] **Step 6: Create `index.html`**

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AI Media Watch</title>
  <link rel="stylesheet" href="/static/styles.css">
  <script src="https://unpkg.com/cytoscape@3.30.2/dist/cytoscape.min.js"></script>
</head>
<body>
  <aside class="sidebar">
    <div class="brand"><span class="logo">AI</span> Media Watch</div>
    <nav>
      <a data-nav="overview" href="#/overview">Overview</a>
      <a data-nav="jobs" href="#/jobs">Jobs</a>
      <a data-nav="investigation" href="#/investigation">Investigation</a>
      <a data-nav="pipeline" href="#/pipeline">Pipeline</a>
      <a data-nav="controls" href="#/controls">Controls</a>
    </nav>
  </aside>
  <main id="view" class="view"></main>
  <script type="module" src="/static/js/app.js"></script>
</body>
</html>
```

- [ ] **Step 7: Create `styles.css`** (dark ops-console base; views extend it)

```css
:root{
  color-scheme: dark;
  --bg:#0f1115; --panel:#181b21; --panel-2:#1f242c; --line:#2c323c;
  --text:#e7eaef; --muted:#9aa3b0; --accent:#ff6b3a; --accent-2:#26c485;
  --good:#26c485; --warn:#ffd166; --bad:#ff6b6b;
}
*{box-sizing:border-box}
body{margin:0;display:grid;grid-template-columns:220px 1fr;min-height:100vh;
  font-family:Inter,system-ui,"Segoe UI",sans-serif;background:var(--bg);color:var(--text)}
a{color:inherit;text-decoration:none}
.muted{color:var(--muted)}
.sidebar{background:var(--panel);border-right:1px solid var(--line);padding:18px 12px;position:sticky;top:0;height:100vh}
.brand{font-weight:800;font-size:16px;display:flex;align-items:center;gap:10px;margin-bottom:18px}
.logo{display:grid;place-items:center;width:30px;height:30px;border-radius:8px;background:rgba(255,107,58,.15);color:var(--accent);font-weight:900}
.sidebar nav{display:grid;gap:4px}
.sidebar nav a{padding:9px 12px;border-radius:8px;color:var(--muted);font-weight:600}
.sidebar nav a:hover{background:var(--panel-2);color:var(--text)}
.sidebar nav a.active{background:rgba(255,107,58,.14);color:var(--accent)}
.view{padding:24px clamp(16px,3vw,40px);display:grid;gap:18px;align-content:start}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:18px}
.card h2{margin:0 0 12px;font-size:16px}
.row{display:flex;flex-wrap:wrap;gap:10px;align-items:center}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}
.kpi{background:var(--panel-2);border:1px solid var(--line);border-radius:10px;padding:14px}
.kpi span{display:block;color:var(--muted);font-size:12px;margin-bottom:6px}
.kpi strong{font-size:22px}
table{width:100%;border-collapse:collapse;font-size:14px}
th,td{border-bottom:1px solid var(--line);padding:9px 8px;text-align:left;vertical-align:top}
th{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.04em}
tbody tr{cursor:default}
tbody tr.clickable:hover{background:var(--panel-2)}
input,select,textarea,button{font:inherit;border-radius:8px}
input,select,textarea{background:#12151a;color:var(--text);border:1px solid var(--line);padding:9px 10px}
textarea{min-height:90px;resize:vertical;width:100%}
button{border:1px solid var(--line);background:var(--accent);color:#1a1206;font-weight:700;padding:9px 14px;cursor:pointer}
button.secondary{background:var(--panel-2);color:var(--text)}
button:disabled{opacity:.55;cursor:wait}
.badge{display:inline-block;border-radius:999px;padding:3px 9px;font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:.03em;border:1px solid var(--line);color:var(--muted)}
.badge.clean{color:var(--good);border-color:rgba(38,196,133,.4);background:rgba(38,196,133,.1)}
.badge.scam{color:var(--bad);border-color:rgba(255,107,107,.4);background:rgba(255,107,107,.1)}
.badge.warn{color:var(--warn);border-color:rgba(255,209,102,.4);background:rgba(255,209,102,.1)}
.bar{height:8px;border-radius:999px;background:var(--panel-2);overflow:hidden}
.bar>i{display:block;height:100%;background:var(--accent)}
.banner{border:1px solid var(--warn);background:rgba(255,209,102,.08);color:var(--warn);border-radius:8px;padding:10px 12px;font-size:13px}
pre{margin:0;padding:12px;border-radius:8px;background:#0b0d10;color:#d7deea;overflow:auto;max-height:300px;font-size:12px}
details summary{cursor:pointer;color:var(--muted);font-size:13px}
@media(max-width:760px){body{grid-template-columns:1fr}.sidebar{height:auto;position:static}}
```

- [ ] **Step 8: Mount static + serve index in the backend**

In `server/app/main.py`, add the import near the top:

```python
from pathlib import Path
from fastapi.staticfiles import StaticFiles
```

In `create_app()`, after the `for module in (...)` include loop and before
`return app`, add:

```python
    static_dir = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
```

- [ ] **Step 9: Replace `ui.py` index, drop the giant strings**

Rewrite `server/app/api/ui.py` so it keeps only the `/`, `/architecture-ui`
redirect, and `/models` routes (delete the `PAGE` and `ARCHITECTURE_PAGE`
string constants entirely):

```python
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse, RedirectResponse

from app.api.deps import get_components

router = APIRouter()

_INDEX = Path(__file__).parent.parent / "static" / "index.html"


@router.get("/")
async def index() -> FileResponse:
    return FileResponse(_INDEX)


@router.get("/architecture-ui")
async def architecture_ui() -> RedirectResponse:
    return RedirectResponse(url="/#/pipeline")


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
```

- [ ] **Step 10: Manual smoke test**

Run: `cd server && uvicorn app.main:app --reload`
Open `http://localhost:8000/`. Expected: dark sidebar with 5 nav links;
clicking each shows the stub card with the view name; URL hash updates; the
active nav link highlights. `http://localhost:8000/architecture-ui` redirects
to `/#/pipeline`. `http://localhost:8000/models` still returns JSON.

- [ ] **Step 11: Run the backend test suite (no regressions)**

Run: `cd server && python -m pytest -q`
Expected: PASS (existing tests + the new ones from Tasks 1-3).

- [ ] **Step 12: Commit**

```bash
git add server/app/static server/app/main.py server/app/api/ui.py
git commit -m "Serve static app shell; replace embedded HTML dashboard"
```

---

## Task 5: Shared components (riskBadge, findings, graph)

**Files:**
- Create: `server/app/static/js/components/riskBadge.js`
- Create: `server/app/static/js/components/findings.js`
- Create: `server/app/static/js/components/graph.js`

**Interfaces:**
- Produces:
  - `riskBadge.js`: `export function categoryBadge(category)` -> HTML string
    (`<span class="badge clean|scam">`); `export function riskClass(score)`
    (`>=0.66 -> scam`, `>=0.33 -> warn`, else `clean`);
    `export function confidenceBar(value)` -> HTML string for a `.bar`.
  - `findings.js`: `export function findingsHtml(findings)` -> HTML grouping
    findings by modality into cards.
  - `graph.js`: `export function renderGraph(container, nodes, edges)` -> builds
    a cytoscape instance (uses global `cytoscape`).

- [ ] **Step 1: Create `riskBadge.js`**

```javascript
// server/app/static/js/components/riskBadge.js
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
```

- [ ] **Step 2: Create `findings.js`**

```javascript
// server/app/static/js/components/findings.js
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
```

Add to `styles.css` (append):

```css
.finding{border-top:1px solid var(--line);padding:10px 0;display:grid;gap:8px}
.finding:first-of-type{border-top:0}
```

- [ ] **Step 3: Create `graph.js`**

```javascript
// server/app/static/js/components/graph.js
const TYPE_COLOR = {
  account: "#ff6b3a", domain: "#58d0ff", telegram: "#26c485",
  phone: "#ffd166", email: "#c792ea", wallet: "#f78c6c",
  social: "#82aaff", avatar: "#f07178",
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
        "background-color": (n) => TYPE_COLOR[n.data("type")] || "#9aa3b0",
        label: "data(label)", color: "#e7eaef", "font-size": 10,
        "text-valign": "center", "text-halign": "right", "text-margin-x": 4 } },
      { selector: "edge", style: {
        width: 1.5, "line-color": "#2c323c", "curve-style": "bezier" } },
    ],
    layout: { name: "cose", animate: false },
  });
}
```

Add to `styles.css` (append):

```css
.graph{height:460px;border:1px solid var(--line);border-radius:10px;background:#0b0d10}
```

- [ ] **Step 4: Manual check (smoke)**

These are imported by later views; verify no syntax errors by loading any page
after wiring (done in Task 7/8). For now confirm the files parse: in the browser
console on `http://localhost:8000/`, run
`import("/static/js/components/findings.js").then(m=>console.log(Object.keys(m)))`.
Expected: logs `["findingsHtml"]`. Repeat for `riskBadge.js`
(`["riskClass","categoryBadge","confidenceBar"]`) and `graph.js` (`["renderGraph"]`).

- [ ] **Step 5: Commit**

```bash
git add server/app/static/js/components server/app/static/styles.css
git commit -m "Add shared frontend components: risk badge, findings, graph"
```

---

## Task 6: Controls view (port existing dashboard controls)

Ports upload / parser / feed / single-reel / auto-scan / dedup / models into the
Controls view. Reuses existing endpoints unchanged.

**Files:**
- Modify (replace stub): `server/app/static/js/views/controls.js`

**Interfaces:**
- Consumes: `api`, `postJson` from `api.js`; endpoints `POST /videos`,
  `POST /parser/start|stop|feed|reel`, `GET /parser/status`,
  `GET|POST /parser/auto-scan`, `POST /dedup/clear`, `GET /models`.
- Produces: `render(mount)`, `stop()` (clears the status poll interval).

- [ ] **Step 1: Implement `controls.js`**

```javascript
// server/app/static/js/views/controls.js
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
  root.querySelector("#startParser").addEventListener("click", async () => {
    const channel = root.querySelector("#channelUrl").value.trim();
    if (!channel) { status.textContent = "Enter a channel."; return; }
    const body = { channel_url: channel };
    const m = num("#maxReels"); if (m) body.max_reels = m;
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
    try { renderParser(root, await postJson("/parser/reel", { reel_url: url })); }
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
```

- [ ] **Step 2: Manual smoke test**

Run server, open `#/controls`. Expected: four cards render; parser status line
updates within 3s; toggling Auto-scan flips ON/OFF and shows "Saved";
threshold/max inputs persist; Models card shows stub/real status. Upload a small
video file -> status shows a link to the new job.

- [ ] **Step 3: Commit**

```bash
git add server/app/static/js/views/controls.js
git commit -m "Controls view: upload, parser, auto-scan, models"
```

---

## Task 7: Jobs list view

**Files:**
- Modify (replace stub): `server/app/static/js/views/jobs.js`

**Interfaces:**
- Consumes: `api` from `api.js`; `GET /recent-jobs`, `GET /review-queue`;
  `categoryBadge`, `riskClass` from `components/riskBadge.js`; `fmt` from `api.js`.
- Produces: `render(mount)`, `stop()`. Merges recent + review-queue items by
  `job_id` (review-queue items win on conflict). Client-side filters: status,
  category, min-risk, text query. Rows link to `#/jobs/{job_id}`.

- [ ] **Step 1: Implement `jobs.js`**

```javascript
// server/app/static/js/views/jobs.js
import { api, fmt } from "../api.js";
import { escapeHtml, fmtTime } from "../util.js";
import { categoryBadge } from "../components/riskBadge.js";

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
        <thead><tr><th>Time</th><th>Reel</th><th>Description</th><th>Status</th><th>Risk</th><th>Category</th></tr></thead>
        <tbody id="rows"><tr><td colspan="6" class="muted">Loading…</td></tr></tbody>
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
      <td>${categoryBadge(it.category)}</td></tr>`;
  });
  mount.querySelector("#rows").innerHTML = rows.length
    ? rows.join("") : '<tr><td colspan="6" class="muted">No matching jobs.</td></tr>';
}
```

- [ ] **Step 2: Manual smoke test**

Open `#/jobs`. Expected: table lists recent jobs; filters narrow rows live;
clicking a row navigates to `#/jobs/<id>`; refreshes every 3s without losing the
typed query.

- [ ] **Step 3: Commit**

```bash
git add server/app/static/js/views/jobs.js
git commit -m "Jobs list view with client-side filters"
```

---

## Task 8: Job Detail view

**Files:**
- Modify (replace stub): `server/app/static/js/views/jobDetail.js`

**Interfaces:**
- Consumes: `api`, `fmt`; `GET /jobs/{id}`, `GET /jobs/{id}/explanations`,
  `GET /jobs/{id}/video`; `findingsHtml` (components/findings.js);
  `categoryBadge`, `riskClass`, `confidenceBar` (components/riskBadge.js).
- Produces: `render(mount, params)` where `params[0]` is the job id; `stop()`
  clears the poll timer. Polls `GET /jobs/{id}` until status `done`/`failed`.

- [ ] **Step 1: Implement `jobDetail.js`**

```javascript
// server/app/static/js/views/jobDetail.js
import { api, fmt } from "../api.js";
import { escapeHtml } from "../util.js";
import { findingsHtml } from "../components/findings.js";
import { categoryBadge, riskClass, confidenceBar } from "../components/riskBadge.js";

let timer = null;

export function render(mount, params) {
  const jobId = decodeURIComponent(params[0]);
  mount.innerHTML = `<div id="jobRoot"><section class="card"><a href="#/jobs">&larr; Jobs</a>
    <h2 style="margin-top:10px">Job ${escapeHtml(jobId)}</h2>
    <p class="muted">Loading…</p></section></div>`;
  poll(mount, jobId);
  timer = setInterval(() => poll(mount, jobId), 1500);
}

export function stop() { if (timer) clearInterval(timer); timer = null; }

async function poll(mount, jobId) {
  let job;
  try { job = await api(`/jobs/${encodeURIComponent(jobId)}`); }
  catch (err) { mount.querySelector("#jobRoot").innerHTML = `<section class="card"><a href="#/jobs">&larr; Jobs</a><p class="banner">${escapeHtml(err.message)}</p></section>`; stop(); return; }

  let explanations = [];
  if (job.status === "done" || job.status === "failed") {
    stop();
    try { explanations = (await api(`/jobs/${encodeURIComponent(jobId)}/explanations`)).explanations || []; } catch (_) {}
  }
  draw(mount, job, explanations);
}

function scannerBars(job) {
  const sc = job.scanner_confidences || job.method_confidences || {};
  const entries = Object.entries(sc);
  if (!entries.length) return '<p class="muted">No scanner scores.</p>';
  return entries.map(([k, v]) => `
    <div style="display:grid;gap:4px">
      <div class="row" style="justify-content:space-between"><span>${escapeHtml(k)}</span><span class="muted">${fmt(v)}</span></div>
      ${confidenceBar(v)}</div>`).join("");
}

function sourceHtml(job) {
  const s = job.source || {};
  const link = s.url || s.permalink || s.top_bar_url;
  const rows = [
    ["Platform", s.platform], ["Shortcode", s.shortcode],
    ["URL", link ? `<a href="${escapeHtml(link)}" target="_blank" rel="noreferrer">open</a>` : null],
  ].filter(([, v]) => v);
  return rows.map(([k, v]) => `<div class="kpi"><span>${k}</span><strong>${k === "URL" ? v : escapeHtml(v)}</strong></div>`).join("");
}

function explanationsHtml(list) {
  if (!list.length) return '<p class="muted">No explanations.</p>';
  return list.map((e) => `
    <div class="finding">
      <strong>${escapeHtml(e.method || "")} <span class="muted">(${escapeHtml(e.scope || "")})</span></strong>
      <p>${escapeHtml(e.summary || "")}</p>
      <details><summary>payload</summary><pre>${escapeHtml(JSON.stringify(e.payload || {}, null, 2))}</pre></details>
    </div>`).join("");
}

function draw(mount, job, explanations) {
  const risk = job.risk_score;
  mount.querySelector("#jobRoot").innerHTML = `
    <section class="card">
      <a href="#/jobs">&larr; Jobs</a>
      <div class="row" style="justify-content:space-between;margin-top:8px">
        <h2>Job ${escapeHtml(job.job_id)}</h2>
        <div class="row">
          <span class="badge ${riskClass(risk)}">risk ${fmt(risk)}</span>
          ${categoryBadge(job.category)}
          <span class="badge">${escapeHtml(job.status || "")}</span>
        </div>
      </div>
      <p class="muted">${escapeHtml(job.description || "")}</p>
    </section>

    <section class="card">
      <h2>Video</h2>
      <video controls style="width:100%;max-height:420px;border-radius:8px;background:#000"
        src="/jobs/${encodeURIComponent(job.job_id)}/video"
        onerror="this.replaceWith(Object.assign(document.createElement('p'),{className:'muted',textContent:'Video not stored; use the source link.'}))"></video>
    </section>

    <section class="card"><h2>Source</h2><div class="kpis">${sourceHtml(job)}</div></section>
    <section class="card"><h2>Scanner confidence</h2><div style="display:grid;gap:10px">${scannerBars(job)}</div></section>
    ${findingsHtml(job.findings)}
    <section class="card"><h2>Explanations</h2>${explanationsHtml(explanations)}</section>`;
}
```

- [ ] **Step 2: Manual smoke test**

From `#/jobs`, click a finished job. Expected: header shows risk badge (color by
score), category badge, status; video plays if stored, else shows the fallback
note; source KPIs; scanner confidence bars; findings grouped by modality with
collapsible evidence; explanations rendered readably. Open an in-progress job ->
the page polls and fills in once it reaches `done`.

- [ ] **Step 3: Commit**

```bash
git add server/app/static/js/views/jobDetail.js
git commit -m "Job detail view: video, findings cards, explanations"
```

---

## Task 9: Overview view

**Files:**
- Modify (replace stub): `server/app/static/js/views/overview.js`

**Interfaces:**
- Consumes: `api`, `fmt`; `GET /recent-jobs`, `GET /review-queue`,
  `GET /parser/status`; `categoryBadge` (components/riskBadge.js);
  `fmtTime` (util.js).
- Produces: `render(mount)`, `stop()`. KPIs computed client-side from
  recent-jobs; recent-activity table links to job detail.

- [ ] **Step 1: Implement `overview.js`**

```javascript
// server/app/static/js/views/overview.js
import { api, fmt } from "../api.js";
import { escapeHtml, fmtTime } from "../util.js";
import { categoryBadge } from "../components/riskBadge.js";

let timer = null;

export function render(mount) {
  mount.innerHTML = `
    <section class="card"><h2>Overview</h2><div id="kpis" class="kpis"></div></section>
    <section class="card"><h2>Recent activity</h2>
      <table><thead><tr><th>Time</th><th>Reel</th><th>Status</th><th>Risk</th><th>Category</th></tr></thead>
      <tbody id="recent"><tr><td colspan="5" class="muted">Loading…</td></tr></tbody></table></section>`;
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
    const scam = items.filter((it) => it.category && it.category !== "clean").length;
    const risks = items.map((it) => it.risk_score).filter((v) => typeof v === "number");
    const avg = risks.length ? risks.reduce((a, b) => a + b, 0) / risks.length : null;
    const kpis = [
      ["Total jobs", items.length],
      ["Flagged scam", scam],
      ["Avg risk", fmt(avg)],
      ["Review queue", (review.items || []).length],
      ["Parser", parser.running ? "running" : "idle"],
    ];
    mount.querySelector("#kpis").innerHTML = kpis.map(([k, v]) => `<div class="kpi"><span>${k}</span><strong>${escapeHtml(v)}</strong></div>`).join("");
    mount.querySelector("#recent").innerHTML = items.slice(0, 15).map((it) => {
      const sc = (it.source && (it.source.shortcode || it.source.platform)) || "-";
      return `<tr class="clickable" onclick="location.hash='#/jobs/${encodeURIComponent(it.job_id)}'">
        <td>${fmtTime(it.created_at)}</td><td>${escapeHtml(sc)}</td>
        <td>${escapeHtml(it.status || "")}</td><td>${fmt(it.risk_score)}</td><td>${categoryBadge(it.category)}</td></tr>`;
    }).join("") || '<tr><td colspan="5" class="muted">No jobs yet.</td></tr>';
  } catch (_) {}
}
```

- [ ] **Step 2: Manual smoke test**

Open `#/overview` (default landing). Expected: 5 KPI cards with live counts;
recent activity table; clicking a row opens job detail; refreshes every 3s.

- [ ] **Step 3: Commit**

```bash
git add server/app/static/js/views/overview.js
git commit -m "Overview view with KPIs and recent activity"
```

---

## Task 10: Investigation view (OSINT + graph + telegram)

**Files:**
- Modify (replace stub): `server/app/static/js/views/investigation.js`

**Interfaces:**
- Consumes: `api`, `postJson`; `GET /osint/graph`, `POST /osint/accounts`,
  `GET /osint/accounts/{job_id}`, `GET /telegram/channels`; `renderGraph`
  (components/graph.js); `escapeHtml`. Each response carries `available: bool`.
- Produces: `render(mount)`, `stop()` (clears the OSINT job poll timer).

- [ ] **Step 1: Implement `investigation.js`**

```javascript
// server/app/static/js/views/investigation.js
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
```

- [ ] **Step 2: Manual smoke test (service offline path)**

With the investigator service NOT running, open `#/investigation`. Expected: the
graph and telegram panels show amber "offline" banners (NOT errors); clicking
Scan shows "Investigator offline". The page never white-screens.

- [ ] **Step 3: Manual smoke test (service online path, if available)**

Start the investigator (`cd invistigator && uvicorn invistigator.api:get_app --factory --port 8010`),
seed at least 2 profiles, reload `#/investigation`. Expected: graph renders nodes
(accounts orange, attributes colored by type) with edges; Scan submits and polls;
profile cards list contacts/domain/socials.

- [ ] **Step 4: Commit**

```bash
git add server/app/static/js/views/investigation.js
git commit -m "Investigation view: OSINT profiles, graph, telegram reports"
```

---

## Task 11: Pipeline view (port the architecture editor)

Ports the existing, working pipeline flow editor from the old `ui.py` logic into
a module. The old JS still exists in git history (commit before Task 4) at
`server/app/api/ui.py` — reference it there.

**Files:**
- Modify (replace stub): `server/app/static/js/views/pipeline.js`

**Interfaces:**
- Consumes: `api`, `postJson`; `GET /architecture`,
  `POST /architecture/node/{id}`, `DELETE /architecture/node/{id}`,
  `POST /architecture/aggregate`, `POST /architecture/reload`,
  `GET|POST /parser/auto-scan`; `escapeHtml`.
- Produces: `render(mount)`, `stop()`.

- [ ] **Step 1: Implement `pipeline.js`**

Port the architecture flow rendering and the `change`/`click` handlers from the
pre-Task-4 `server/app/api/ui.py` (`loadArchitecture`, `pipelineNodeHtml`,
`aggregateNodeHtml`, `investigateNodeHtml`, `stageColHtml`, `renderFlow`,
`postNode`, `deleteNode`, reload handler, and the `document`-level `change`
handler for `nodeToggle`/`nodeThreshold`/`defaultThreshold`/`invToggle`/`invMax`/`invTh`).
Scope the listeners to `mount` (not `document`) and use the module's flow
container. Concretely:

```javascript
// server/app/static/js/views/pipeline.js
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
```

- [ ] **Step 2: Add pipeline styles** (append to `styles.css`)

```css
.flow{display:flex;align-items:flex-start;gap:0;overflow-x:auto;padding-bottom:8px}
.stage{display:grid;gap:10px;min-width:210px;max-width:240px}
.stage-head{font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);font-weight:800}
.stage-arrow{display:flex;align-items:center;color:var(--line);font-size:22px;padding:0 10px}
.node{border:1px solid var(--line);border-radius:8px;background:var(--panel-2);padding:10px 12px;display:grid;gap:8px}
.node.off{opacity:.6}.node.err{border-color:var(--bad)}
.node.info{border-style:dashed;color:var(--muted)}
.node-title{font-weight:700}
.err-msg{color:var(--bad);font-size:12px}
```

- [ ] **Step 3: Manual smoke test**

Open `#/pipeline`. Expected: stages render left-to-right with arrows; toggling a
checker, editing a threshold, the aggregator default, and the investigator
controls all show "Saved" and persist on reload; Reload plugins works; a
removable plugin node can be removed.

- [ ] **Step 4: Commit**

```bash
git add server/app/static/js/views/pipeline.js server/app/static/styles.css
git commit -m "Pipeline view: ported architecture flow editor"
```

---

## Task 12: Full smoke pass + cleanup

**Files:**
- (No new files) — verification + any small fixes uncovered.

- [ ] **Step 1: Backend tests green**

Run: `cd server && python -m pytest -q`
Expected: PASS (all tests, including Tasks 1-3).

- [ ] **Step 2: End-to-end manual walk**

Run: `cd server && MW_RUN_WORKERS_INLINE=true uvicorn app.main:app --reload`
(or set `MW_QUEUE_BACKEND`/workers per the repo's normal dev flow). Walk:
Overview -> Jobs (filter) -> Job Detail (upload via Controls first) ->
Investigation (offline banners) -> Pipeline (toggle a checker). Confirm no
console errors and every view polls/refreshes without losing focus.

- [ ] **Step 3: Confirm old routes**

`GET /` returns the new app; `GET /architecture-ui` redirects to `/#/pipeline`;
`GET /models` returns JSON. No reference to `PAGE`/`ARCHITECTURE_PAGE` remains:
Run: `cd server && grep -rn "ARCHITECTURE_PAGE\|PAGE =" app/` -> Expected: no matches.

- [ ] **Step 4: Commit any fixes**

```bash
git add -A
git commit -m "Smoke-pass fixes for dashboard rebuild"
```

---

## Self-Review Notes (coverage vs spec)

- Static layout + StaticFiles + index at `/` — Task 4. ✓
- Video endpoint with fallback — Task 3 (backend) + Task 8 (UI fallback). ✓
- Investigation proxy `/osint/*`, `/telegram/*` + graceful degradation — Task 2. ✓
- Config `MW_INVESTIGATOR_URL`/`MW_TELEGRAM_URL` — Task 1. ✓
- 6 views (Overview, Jobs, Job Detail, Investigation, Pipeline, Controls) — Tasks 4-11. ✓
- Readable findings/explanations — Tasks 5 + 8. ✓
- Investigation graph (cytoscape) — Tasks 5 + 10. ✓
- Dark ops-console theme — Task 4 (`styles.css`). ✓
- Tests for proxy + video — Tasks 2, 3. ✓
- `/architecture-ui` redirect kept — Task 4. ✓
