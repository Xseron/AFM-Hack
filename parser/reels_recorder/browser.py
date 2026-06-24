"""Connect to the anti-detect browser over CDP; session backup; logged-out guard."""
from __future__ import annotations

import json
import os

from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

from .cli import Config, LOGIN_MARKERS, REELS_URL


class BrowserConnectError(RuntimeError):
    pass


def connect(cfg: Config):
    """Return (playwright, browser, context, page) attached to the running profile."""
    pw = sync_playwright().start()
    try:
        browser: Browser = pw.chromium.connect_over_cdp(cfg.cdp_url)
    except Exception as e:  # noqa: BLE001
        pw.stop()
        raise BrowserConnectError(
            f"Could not connect to the anti-detect browser at {cfg.cdp_url}. "
            f"Start the profile with remote debugging enabled. ({e})"
        ) from e

    if not browser.contexts:
        pw.stop()
        raise BrowserConnectError("Connected, but the browser has no open context/window.")
    context: BrowserContext = browser.contexts[0]

    page = _pick_reels_page(context)
    return pw, browser, context, page


def _pick_reels_page(context: BrowserContext) -> Page:
    pages = list(context.pages)
    # Prefer a page already on instagram; else the first page; else open one.
    for p in pages:
        if "instagram.com" in (p.url or ""):
            return p
    if pages:
        return pages[0]
    return context.new_page()


def ensure_reels_feed(page: Page, cfg: Config) -> None:
    """Navigate to the Reels feed if we are not already somewhere on instagram reels."""
    url = page.url or ""
    if "/reels" not in url and "/reel/" not in url:
        page.goto(REELS_URL, wait_until="domcontentloaded")
    page.wait_for_timeout(1500)


def is_logged_out(page: Page) -> bool:
    for sel in LOGIN_MARKERS:
        try:
            if page.locator(sel).first.is_visible():
                return True
        except Exception:  # noqa: BLE001
            continue
    return False


def save_session(context: BrowserContext, cfg: Config) -> None:
    os.makedirs(cfg.state_dir, exist_ok=True)
    path = os.path.join(cfg.state_dir, "instagram_session.json")
    try:
        state = context.storage_state()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f)
    except Exception as e:  # noqa: BLE001
        print(f"[warn] could not save session backup: {e}")
