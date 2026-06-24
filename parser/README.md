# parser — Instagram Reels recorder + humanizer

Records each Instagram Reel as a separate video via a Playwright-driven **anti-detect
browser**, dedups by shortcode, uploads to the AI Media Watch backend (`POST /videos`),
and imitates human behaviour (skip-early, like, comments, follow).

## Setup

```bash
cd parser
python -m pip install -r requirements.txt
python -m playwright install chromium   # only if your anti-detect browser isn't used for CDP
```

## Run

1. Start your **anti-detect browser** with remote debugging (CDP) enabled, log in to
   Instagram, and open the Reels feed (`instagram.com/reels/`).
2. Run:

```bash
# Dry run: pretends to upload, exercises like/comment/follow (server assumed True)
python -m reels_recorder --debug --max-reels 3

# Live: uploads to the backend, performs NO likes/follows until a real decision
# endpoint is wired (get_decisions is a safe stub returning all-false in live mode)
python -m reels_recorder --server-url http://localhost:8000
```

### Flags

| Flag | Default | Meaning |
|------|---------|---------|
| `--debug` | off | No HTTP upload; prints `[debug] pretend sent …`; all actions enabled |
| `--cdp-url` | `http://localhost:9222` | CDP endpoint of the anti-detect browser |
| `--server-url` | `http://localhost:8000` | Backend base URL |
| `--out` | `recordings` | Where `.webm` clips are saved |
| `--max-reels` | unlimited | Stop after N new reels |

## Behaviour

- **Per reel:** record active `<video>` → watch (sometimes skip early) → upload watched
  portion → like / comments (20%) / follow (5%), each gated by the server decision.
- **Dedup:** by reel shortcode, persisted to `state/seen_reels.json`.
- **Idle watchdog:** if 60s pass without scrolling, force-scroll and start a fresh recording.
- **Session:** inherited from the anti-detect profile; backed up to
  `state/instagram_session.json`. No auto-login (it aborts if logged out).
- `✓ sent to server: <shortcode> (<N> KB)` prints on each upload.

## Notes / known limits

- Selectors carry EN + RU labels (`cli.py`); add your UI language there if buttons aren't found.
- Recording uses `video.captureStream()`; if Instagram serves a CORS-tainted stream the clip
  comes back empty (logged, upload skipped). ffmpeg window-capture is the documented fallback,
  not yet built.

See `docs/superpowers/specs/2026-06-24-instagram-reels-recorder-design.md` for the full design.
