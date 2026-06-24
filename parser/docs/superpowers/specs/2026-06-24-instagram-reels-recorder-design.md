# Instagram Reels Recorder + Humanizer — Design

**Date:** 2026-06-24
**Component:** `hakaton/parser`
**Purpose:** Collect Instagram Reels for the AI Media Watch backend by screen-recording each
reel (or the watched portion of it) and uploading it to `POST /videos`, while imitating
human behavior so Instagram does not flag the session as a bot.

## Stack & environment

- **Language:** Python 3.12 (matches the backend).
- **Automation:** Playwright (sync API) connecting to an **anti-detect browser** that is
  already running, logged in, and on `https://www.instagram.com/reels/`, via
  `playwright.chromium.connect_over_cdp(<cdp-url>)`.
- **Recording:** in-page `MediaRecorder` on the active reel's `<video>` element
  (`video.captureStream()` → webm). One file per reel; partial clips when a reel is skipped
  early. No OS-level screen capture and no fixed window position required.
- **Not used:** crawl4ai (content-extraction tool, cannot record video or do stateful
  interaction); ffmpeg window-capture (documented fallback only, not built).

## Why these choices

- `connect_over_cdp` to the anti-detect profile means we never log in ourselves (the most
  ban-prone action) and we inherit a persistent, warmed-up fingerprint + cookies.
- `MediaRecorder` on the `<video>` is the only recording method that naturally produces one
  file per reel **and** captures exactly the portion that played — required by the
  "skip early, still upload the watched part" rule.
- Dedup by **shortcode** (from the reel's `/reel/<code>/` link) is more reliable than video
  hashing and lets us avoid re-recording across runs.

## Modules

Each module has one clear purpose and a small interface.

### `cli.py`
- Parses args and holds tunable constants.
- Flags:
  - `--debug` — pretend to upload (no real HTTP), and `get_decisions` returns all `True` so
    like/comment/follow logic is exercised.
  - `--cdp-url` (default `http://localhost:9222`) — anti-detect browser CDP endpoint.
  - `--server-url` (default `http://localhost:8000`) — backend base URL.
  - `--out` (default `parser/recordings`) — directory for saved `.webm` clips.
  - `--max-reels` (optional int) — stop after N new reels (for testing).
- Holds the **selectors + timing config** block (see "Configuration constants").

### `browser.py`
- `connect(cdp_url) -> (playwright, browser, context, page)`: connect over CDP, pick the
  active page, assert URL is the Reels feed.
- `save_session(context, path)`: dump `context.storage_state()` to
  `parser/state/instagram_session.json` as a backup.
- `is_logged_out(page) -> bool`: detect a login form; if logged out, **abort** before doing
  anything bot-like (no auto re-login).

### `recorder.py`
- Injects a JS controller exposed as `window.__rec` with:
  - `start()` — find the active `<video>`, `captureStream()`, start `MediaRecorder`.
  - `stop()` — stop and return the clip as base64 (chunks joined into one Blob).
- Python wrappers: `start_recording(page)`, `stop_recording(page) -> bytes` (base64 decode).
- If a returned clip is empty (CORS-tainted stream), log a clear warning and return `b""`;
  the reel is then skipped for upload (with a logged reason).

### `feed.py`
- `active_reel(page)` → handle/locator for the reel currently in view.
- `shortcode(reel)` → dedup key from the `/reel/<code>/` link; `None` if not found.
- `caption(reel)` → caption text for the upload `description` (fallback to a placeholder so
  the server's non-empty-description rule is satisfied).
- `find_like(reel)`, `find_comment(reel)`, `find_follow(reel)` → button locators scoped to
  the active reel, matched by `aria-label`/text (EN + RU labels from config).
- `scroll_next(page)` → advance to the next reel (keyboard ArrowDown / wheel; human-like).

### `actions.py`
- `like(reel)` — click like if not already liked.
- `open_comments_then_close(reel, page)` — open comments, wait a random 2–5s, then close by
  clicking the top/outside area (mobile "tap top" equivalent on web).
- `follow(reel)` — click follow if the button shows the not-following state.

### `humanize.py`
- `watch_plan()` → either watch (near-)full, or **skip early** at a random fraction.
- `inter_reel_delay()`, comment-open probability **20%**, follow probability **5%**, the
  2–5s comment dwell, and small jitter on all waits.
- All randomness centralized so behavior tuning lives in one place.

### `server_client.py`
- `upload(video: bytes, description: str, meta: dict) -> dict`:
  - Normal: `POST {server-url}/videos` (multipart: `video`, `description`, `source_platform`,
    `source_url`, `source_meta`). Prints `✓ sent to server: <shortcode> (<N> KB)`.
  - `--debug`: skips HTTP, prints `[debug] pretend sent: <shortcode> (<N> KB)`, returns a
    fake `{"job_id": "...", "duplicate": false}`.
- `get_decisions(reel_meta) -> {"like": bool, "comment": bool, "follow": bool}`:
  - `--debug`: all `True`.
  - Normal: **safe stub** returning all `False` (no likes/comments/follows). This is the
    single seam to wire the real endpoint to later.

### `main.py`
- Orchestration loop + the 60s idle watchdog (see "Per-reel flow").

## Per-reel flow

1. Identify the active reel → `shortcode`. If already in the seen-set → `scroll_next`, skip.
   Otherwise add to seen-set (persisted to `parser/state/seen_reels.json`).
2. `start_recording`.
3. `watch_plan()`: watch full, or skip early at a random fraction. Poll in small steps.
4. On done/skip → `stop_recording` → bytes (partial is acceptable and expected).
5. `get_decisions(meta)`.
6. If bytes non-empty → `upload(bytes, caption, meta)` and print the sent line. (Empty/tainted
   clip → log + skip upload.)
7. Behavior, gated by decisions:
   - `like` → `like(reel)`.
   - `comment` → with **20%** probability: `open_comments_then_close` (waits 2–5s).
   - `follow` → with **5%** probability: `follow(reel)`.
8. `inter_reel_delay()` → `scroll_next`.

### Idle watchdog
- Track `last_scroll_at`. If now − `last_scroll_at` > **60s**, force `scroll_next` and start a
  fresh recording on the new active reel. Prevents getting stuck on one reel.

## Configuration constants (one block in `cli.py`)

- Reel feed URL prefix.
- Selectors (EN + RU): like (`Like`/`Нравится`), comment (`Comment`/`Комментировать`),
  follow (`Follow`/`Подписаться`), reel link (`a[href*="/reel/"]`), login-form marker.
- Timings: max dwell 60s, comment dwell 2–5s, inter-reel delay range, skip-early fraction
  range, comment prob 0.20, follow prob 0.05.

## Persistence / state files (under `parser/state/`)

- `seen_reels.json` — set of shortcodes already recorded (cross-run dedup).
- `instagram_session.json` — `storage_state()` backup.

## Error handling

- **Logged out** → abort immediately with a clear message; never auto-login.
- **Empty/tainted clip** → warn, skip upload, continue (note ffmpeg fallback as future work).
- **Selector miss** (button not found) → log and continue; never crash the loop on one reel.
- **Upload failure** → log, keep the local `.webm`, continue.
- **CDP connect failure** → clear message telling the user to start the anti-detect profile.

## Out of scope (now)

- Real `get_decisions` server endpoint (safe stub until it exists).
- ffmpeg window-capture fallback.
- Near-duplicate (perceptual) dedup — server handles SHA-256; we dedup by shortcode.
- Automatic login / account creation.

## Testing approach

- `humanize.py` probability gates and `watch_plan` — pure functions, unit-testable with a
  seeded RNG.
- `feed.shortcode` / `caption` parsing — unit test against saved HTML snippets.
- `server_client` debug-mode output — unit test that no HTTP is attempted and the printed
  line is correct.
- End-to-end against a live anti-detect browser is manual (`--debug --max-reels 3`).
