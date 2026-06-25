# AI Media Watch — Embedded Dashboard Rebuild

**Date:** 2026-06-25
**Status:** Approved design, pending implementation plan

## Goal

Rebuild the embedded operator dashboard (served from the main FastAPI server on
`:8000`) so the **full system is visible and usable**: a proper Jobs list and
detail view, readable findings/explanations, OSINT results, an investigation
graph, the existing pipeline editor, and a unified visual polish.

The frontend stays **embedded in the main server** (no separate SPA, no build
step). The current monolithic HTML string in `server/app/api/ui.py`
(~1630 lines) is replaced by static files served via `StaticFiles`.

## Non-Goals (YAGNI)

- No React / Vite / build pipeline.
- No n8n workflow integration (no workflow files exist; out of scope).
- No authentication / multi-user.
- No historical browsing of OSINT batches beyond what existing endpoints return.

## Architecture

### Frontend code layout

```
server/app/static/
  index.html          # shell: sidebar nav + <main> mount point
  styles.css          # unified dark "ops-console" theme
  js/
    api.js            # fetch wrapper, error normalization
    router.js         # tiny hash router (#/overview, #/jobs, #/jobs/:id, ...)
    app.js            # bootstrap: wire router -> views, global polling
    views/
      overview.js
      jobs.js
      jobDetail.js
      investigation.js
      pipeline.js     # ported from current architecture flow logic
      controls.js     # upload / parser / feed / reel / auto-scan / dedup / models
    components/
      graph.js        # cytoscape.js wrapper (CDN-loaded)
      findings.js     # finding cards by modality + confidence bars
      riskBadge.js    # shared risk/category/status indicators
```

- ES modules (`<script type="module">`), vanilla JS, no framework.
- `cytoscape.js` loaded from CDN for the investigation graph.
- Hash-based routing; no server-side routing changes for views.

### Server changes

1. **Mount static files.** In `create_app()` (`server/app/main.py`):
   serve `server/app/static/` and return `index.html` at `/`.
   - The current `ui.py` `PAGE`/`ARCHITECTURE_PAGE` strings are removed; the
     `ui` router either becomes a thin redirect/index handler or is dropped in
     favor of the static mount. `/architecture-ui` folds into the `#/pipeline`
     view (keep a redirect from `/architecture-ui` -> `/#/pipeline` for any
     bookmarks).

2. **Video streaming endpoint** (new, on the existing `jobs` router):
   - `GET /jobs/{job_id}/video` -> `FileResponse(buffer_path)` when the buffered
     file exists locally; `404` otherwise. The Job Detail view tries the player
     and falls back to the source link/shortcode when 404.

3. **Investigation proxy router** (`server/app/api/investigation.py`, new,
   included in `main.py`). Forwards to the separate services so the browser
   never talks to them directly (avoids CORS) and **degrades gracefully** when a
   service is offline:
   - `GET  /osint/graph?min_shared=2`        -> `INVESTIGATOR_URL/graph`
   - `GET  /osint/accounts/{job_id}`         -> `INVESTIGATOR_URL/accounts/{job_id}`
   - `POST /osint/accounts`                  -> `INVESTIGATOR_URL/accounts`
   - `GET  /telegram/channels`               -> `TELEGRAM_URL/channels`
   - `GET  /telegram/channels/{username}`    -> `TELEGRAM_URL/channels/{username}`
   - Each handler uses a short `httpx` timeout inside try/except. On connection
     error / timeout it returns `200 {"available": false, "reason": "<msg>"}`
     so the UI shows an inline "service offline" banner instead of erroring.
     On success it returns `{"available": true, ...upstream payload...}`.

4. **Config** (`server/app/config.py`): add
   - `MW_INVESTIGATOR_URL` (default `http://localhost:8010`)
   - `MW_TELEGRAM_URL` (default `http://localhost:8000` per investigator's
     existing `crawler_url` default — confirm at implementation; make it its own
     setting so it can be pointed elsewhere).

## Data sources (existing endpoints reused)

- `POST /videos`, `GET /jobs/{id}`, `GET /jobs/{id}/explanations`
- `GET /review-queue`, `GET /priority-list`, `GET /recent-jobs`
- `GET /architecture`, `POST/DELETE /architecture/...`, `POST /architecture/reload`
- `GET/POST /parser/*`, `GET/POST /parser/auto-scan`, `POST /parser/feed|reel|start|stop`
- `GET /models`, `POST /dedup/clear`
- New: `GET /jobs/{id}/video`, `/osint/*`, `/telegram/*`

## Views

1. **Overview** — KPI cards (total jobs, flagged-scam count, average risk,
   queue depth, parser running/idle) + recent-activity feed. Polls every 3s.
2. **Jobs** — unified table merged from `/recent-jobs` + `/review-queue`.
   Client-side filters: status, category, min risk, text search
   (description + shortcode). Row click -> Job Detail. Polls every 3s.
3. **Job Detail** (`#/jobs/:id`) — header with risk gauge, category badge,
   status; video player (`/jobs/:id/video`, fallback to source link); source
   metadata (platform, shortcode, url, permalink); per-scanner confidence bars;
   **findings as cards grouped by modality** (text/audio/ocr/visual/triage) with
   confidence bars, `ts_in_video`, readable evidence + collapsible raw JSON;
   readable explanations (scope/method/summary + collapsible payload). Polls
   while status not `done`/`failed`.
4. **Investigation** — OSINT panel: trigger an account scan
   (`POST /osint/accounts`), poll `GET /osint/accounts/{job_id}`, render
   `ProfileData` (contacts: phones/emails/whatsapp/wallets/socials; domain +
   WHOIS age/registrar/redirect chain; cross-platform `accounts_found`;
   telegram links; avatar phash). **Investigation graph** via cytoscape
   (`GET /osint/graph`): bipartite account <-> shared-attribute, node color by
   type, edge by `kind`. Telegram risk reports (`GET /telegram/channels`):
   per-channel risk score, categories, per-post evidence quotes. Each panel
   shows an "offline" banner if its service is down.
5. **Pipeline** — the existing architecture flow editor (enable/disable
   checkers, thresholds, aggregator default, investigator auto-scan tuning,
   reload plugins, remove nodes), ported from current `ui.py` logic.
6. **Controls** — upload video, parser control (start/stop, channel, max reels),
   browse global feed, check single reel, auto-scan config, clear dedup, model
   status pills. Regrouped from current dashboard sections.

## Theme / polish

Single **dark "ops-console" theme** (unifies today's split light dashboard /
dark architecture page). Left sidebar nav, card surfaces, risk color tokens:
green `clean`, amber `warn`, red `scam`. Confidence shown as horizontal bars.
Specific typography/spacing decided during implementation (frontend-design
guidance).

## Error handling

- All `/osint/*` and `/telegram/*` proxy calls degrade to
  `{"available": false}` -> per-panel offline banner.
- `/jobs/:id/video` 404 -> player hidden, source link shown.
- Existing graceful fetch patterns (try/catch, status messages) preserved.

## Testing

- **pytest** for the new proxy router: mock `httpx` for (a) service up ->
  `available: true` passthrough, (b) connection error / timeout ->
  `available: false`. Test `/jobs/:id/video` returns file when present and 404
  when `buffer_path` missing.
- **Manual smoke**: run the server, walk each of the 6 views, confirm polling,
  filters, job detail rendering, and graceful degradation with the investigator
  service stopped.

## Open items to confirm during implementation

- Exact `MW_TELEGRAM_URL` default port (investigator's `crawler_url` default is
  `http://localhost:8000`, which collides with the main server — pick a distinct
  default such as `:8020` and document running the crawler there).
- Whether `buffer_path` is reliably local under the default `local` storage
  backend (it is for `MW_STORAGE_BACKEND=local`); for `s3` the video endpoint
  returns 404 and UI falls back to source link.
