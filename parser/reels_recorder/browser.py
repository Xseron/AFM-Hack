"""Connect to the anti-detect browser over CDP; session backup; logged-out guard."""
from __future__ import annotations

import json
import os

from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

from .cli import Config, INSTAGRAM_REELS_URL, LOGIN_MARKERS, TIKTOK_FEED_URL


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

    page = _pick_platform_page(context, cfg.platform)
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


def _pick_platform_page(context: BrowserContext, platform: str) -> Page:
    pages = list(context.pages)
    domain = "tiktok.com" if platform == "tiktok" else "instagram.com"
    for p in pages:
        if domain in (p.url or ""):
            return p
    return _pick_reels_page(context)


def ensure_reels_feed(page: Page, cfg: Config) -> None:
    """Navigate to the Reels feed if we are not already somewhere on instagram reels."""
    url = page.url or ""
    if "/reels" not in url and "/reel/" not in url:
        page.goto(INSTAGRAM_REELS_URL, wait_until="domcontentloaded")
    page.wait_for_timeout(1500)


def ensure_feed(page: Page, cfg: Config) -> None:
    if cfg.platform == "tiktok":
        url = page.url or ""
        if "tiktok.com" not in url:
            page.goto(TIKTOK_FEED_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)
        return
    ensure_reels_feed(page, cfg)


def login_if_needed(page: Page, cfg: Config) -> bool:
    if cfg.platform == "tiktok":
        return _tiktok_login_if_needed(page, cfg)
    if not is_logged_out(page):
        return True
    if not cfg.auto_login:
        return False
    if not cfg.instagram_username or not cfg.instagram_password:
        print("[error] Instagram login required, but credentials are missing in .env")
        return False

    page.goto("https://www.instagram.com/accounts/login/", wait_until="domcontentloaded")
    page.wait_for_timeout(1500)
    try:
        page.locator('input[name="username"]').fill(cfg.instagram_username, timeout=10000)
        page.locator('input[name="password"]').fill(cfg.instagram_password, timeout=10000)
        try:
            page.get_by_role("button", name="Log in").click(timeout=5000)
        except Exception:  # noqa: BLE001
            page.locator('button[type="submit"]').click(timeout=5000)
    except Exception as e:  # noqa: BLE001
        print(f"[error] could not submit Instagram login form: {e}")
        return False

    for _ in range(60):
        page.wait_for_timeout(1000)
        if not is_logged_out(page):
            page.goto(INSTAGRAM_REELS_URL, wait_until="domcontentloaded")
            page.wait_for_timeout(1500)
            return not is_logged_out(page)

    print("[error] Instagram still shows login/checkpoint. Complete verification in Chrome, then rerun the bot.")
    return False


def is_logged_out(page: Page) -> bool:
    for sel in LOGIN_MARKERS:
        try:
            if page.locator(sel).first.is_visible():
                return True
        except Exception:  # noqa: BLE001
            continue
    return False


def _tiktok_login_if_needed(page: Page, cfg: Config) -> bool:
    # TikTok's public feed often works logged out. If a login wall appears and
    # credentials are configured, make a best-effort login; otherwise continue so
    # manual sessions and public browsing still work.
    if not _tiktok_login_wall_visible(page):
        return True
    if not cfg.auto_login:
        print("[error] TikTok login prompt visible. Log in manually in Chrome or rerun with --auto-login.")
        return False
    if not cfg.tiktok_username or not cfg.tiktok_password:
        print("[error] TikTok login requested, but TIKTOK_USERNAME/TIKTOK_PASSWORD are missing.")
        return False

    page.goto("https://www.tiktok.com/login/phone-or-email/email", wait_until="domcontentloaded")
    page.wait_for_timeout(2000)
    try:
        _fill_first(page, [
            'input[name="username"]',
            'input[autocomplete="username"]',
            'input[type="text"]',
            'input[type="email"]',
        ], cfg.tiktok_username)
        _fill_first(page, [
            'input[type="password"]',
            'input[autocomplete="current-password"]',
        ], cfg.tiktok_password)
        try:
            page.get_by_role("button", name="Log in").click(timeout=5000)
        except Exception:  # noqa: BLE001
            page.locator('button[type="submit"]').click(timeout=5000)
    except Exception as e:  # noqa: BLE001
        print(f"[warn] could not submit TikTok login form: {e}")
        return False

    for _ in range(90):
        page.wait_for_timeout(1000)
        if not _tiktok_login_wall_visible(page):
            page.goto(TIKTOK_FEED_URL, wait_until="domcontentloaded")
            page.wait_for_timeout(2000)
            return True

    print("[error] TikTok still shows login/checkpoint. Complete verification in Chrome, then rerun the bot.")
    return False


def _fill_first(page: Page, selectors: list[str], value: str) -> None:
    last_error: Exception | None = None
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            loc.fill(value, timeout=5000)
            return
        except Exception as e:  # noqa: BLE001
            last_error = e
    raise RuntimeError(f"no login input found: {last_error}")


def _tiktok_login_wall_visible(page: Page) -> bool:
    try:
        if "/login" in (page.url or ""):
            return True
        if "tiktok" in (page.url or "") and "\u0440\u0435\u0433\u0438\u0441\u0442\u0440\u0430\u0446\u0438\u044f" in page.title().lower():
            return True
        if page.locator('[data-e2e="login-modal"]').first.is_visible(timeout=500):
            return True
        if page.locator('input[type="password"]').first.is_visible(timeout=500):
            return True
        if page.get_by_role("button", name="Log in").first.is_visible(timeout=500):
            return True
    except Exception:  # noqa: BLE001
        pass
    return False


def save_session(context: BrowserContext, cfg: Config) -> None:
    os.makedirs(cfg.state_dir, exist_ok=True)
    path = os.path.join(cfg.state_dir, f"{cfg.platform}_session.json")
    try:
        state = context.storage_state()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f)
    except Exception as e:  # noqa: BLE001
        print(f"[warn] could not save session backup: {e}")
