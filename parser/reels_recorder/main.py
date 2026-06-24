"""Orchestration loop: record each new reel, upload it, behave like a human."""
from __future__ import annotations

import os
import sys
import time

from playwright.sync_api import Page

from . import actions, browser, feed, humanize, recorder
from .cli import Config, parse_args
from .server_client import ServerClient
from .state import SeenStore


def _watch(page: Page, cfg: Config) -> None:
    """Watch the active reel until its plan ends, the video ends, or the watchdog fires."""
    plan = humanize.watch_plan(cfg)
    prog = recorder.video_progress(page)
    duration = prog["duration"] if prog else 0.0
    target = humanize.target_seconds(cfg, plan, duration)
    start = time.monotonic()
    while True:
        elapsed = time.monotonic() - start
        if elapsed >= target or elapsed >= cfg.max_dwell:
            break
        prog = recorder.video_progress(page)
        if prog and prog.get("ended"):
            break
        if prog and not plan.skip_early and duration and prog["currentTime"] >= duration * 0.97:
            break
        time.sleep(cfg.poll_step)


def _handle_reel(page: Page, cfg: Config, client: ServerClient, code: str) -> None:
    permalink = f"https://www.instagram.com/reel/{code}/"
    top_bar_url = page.url or permalink
    meta = {
        "shortcode": code,
        "source_url": top_bar_url,
        "top_bar_url": top_bar_url,
        "permalink": permalink,
    }
    cap = feed.caption(page, code)

    recorder.install(page)
    if not recorder.start_recording(page):
        print(f"[warn] could not start recording for {code}; skipping")
        return

    _watch(page, cfg)

    clip = recorder.stop_recording(page)
    if not clip:
        print(f"[warn] empty clip for {code} (stream may be CORS-tainted); skipped upload")
        return

    _save_local(cfg, code, clip)
    client.upload(clip, cap, meta)

    decisions = client.get_decisions(meta)
    if decisions.get("like"):
        if actions.like(page, cfg):
            print(f"  · liked {code}")
    if decisions.get("comment") and humanize.gate(cfg.comment_prob):
        if actions.open_comments_then_close(page, cfg):
            print(f"  · opened comments {code}")
    if decisions.get("follow") and humanize.gate(cfg.follow_prob):
        if actions.follow(page, cfg):
            print(f"  · followed author of {code}")


def _save_local(cfg: Config, code: str, clip: bytes) -> None:
    os.makedirs(cfg.out_dir, exist_ok=True)
    path = os.path.join(cfg.out_dir, f"{code}.webm")
    try:
        with open(path, "wb") as f:
            f.write(clip)
    except Exception as e:  # noqa: BLE001
        print(f"[warn] could not save local clip {path}: {e}")


def run(cfg: Config) -> int:
    os.makedirs(cfg.state_dir, exist_ok=True)
    seen = SeenStore(cfg)
    client = ServerClient(cfg)

    try:
        pw, browser_, context, page = browser.connect(cfg)
    except browser.BrowserConnectError as e:
        print(f"[error] {e}")
        return 2

    try:
        browser.ensure_reels_feed(page, cfg)
        if not browser.login_if_needed(page, cfg):
            print("[error] session looks logged out. Log in manually first or enable INSTAGRAM_AUTO_LOGIN.")
            return 3
        browser.save_session(context, cfg)

        mode = "DEBUG" if cfg.debug else "LIVE"
        print(f"[{mode}] watching Reels. server={cfg.server_url}  out={cfg.out_dir}")

        recorded = 0
        last_scroll = time.monotonic()
        misses = 0
        while True:
            code = feed.shortcode(page)

            # Idle watchdog: if a minute passed without scrolling, move on.
            if time.monotonic() - last_scroll > cfg.max_dwell:
                feed.scroll_next(page)
                last_scroll = time.monotonic()
                page.wait_for_timeout(800)
                continue

            if not code:
                misses += 1
                if misses > 5:
                    print("[warn] no reel detected; is the Reels feed open?")
                    misses = 0
                feed.scroll_next(page)
                last_scroll = time.monotonic()
                page.wait_for_timeout(1000)
                continue
            misses = 0

            if seen.has(code):
                feed.scroll_next(page)
                last_scroll = time.monotonic()
                page.wait_for_timeout(700)
                continue

            seen.add(code)
            _handle_reel(page, cfg, client, code)
            recorded += 1

            if cfg.max_reels and recorded >= cfg.max_reels:
                print(f"[done] reached --max-reels={cfg.max_reels}")
                break

            humanize.sleep_range(cfg.inter_reel_delay)
            feed.scroll_next(page)
            last_scroll = time.monotonic()
            page.wait_for_timeout(800)
    except KeyboardInterrupt:
        print("\n[stop] interrupted by user")
    finally:
        try:
            pw.stop()
        except Exception:  # noqa: BLE001
            pass
    return 0


def main(argv: list[str] | None = None) -> int:
    return run(parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
