"""Locate the active reel: shortcode (dedup key), caption, action buttons, scrolling."""
from __future__ import annotations

import random
import re

from playwright.sync_api import Locator, Page

from .cli import Config

# Feed URLs are /reels/<code>/ (plural); permalinks are /reel/<code>/ (singular).
_SHORTCODE_RE = re.compile(r"/reels?/([A-Za-z0-9_-]+)")


def shortcode(page: Page) -> str | None:
    """Dedup key for the active reel. URL is most reliable; DOM link is the fallback."""
    m = _SHORTCODE_RE.search(page.url or "")
    if m:
        return m.group(1)
    try:
        href = page.locator('a[href*="/reel"]').first.get_attribute("href", timeout=1000)
        if href:
            m = _SHORTCODE_RE.search(href)
            if m:
                return m.group(1)
    except Exception:  # noqa: BLE001
        pass
    return None


def caption(page: Page, code: str | None) -> str:
    """Best-effort caption text for the upload description (server needs it non-empty)."""
    js = """
    () => {
      const vids = Array.from(document.querySelectorAll('video'));
      if (!vids.length) return '';
      const visArea = (el) => { const r = el.getBoundingClientRect();
        const w = Math.max(0, Math.min(r.right, innerWidth) - Math.max(r.left, 0));
        const h = Math.max(0, Math.min(r.bottom, innerHeight) - Math.max(r.top, 0));
        return w * h; };
      const v = vids.slice().sort((a, b) => visArea(b) - visArea(a))[0];
      let node = v.closest('article') || v.closest('div[role="dialog"]') || document.body;
      const spans = Array.from(node.querySelectorAll('h1, span, span[dir]'));
      let best = '';
      for (const s of spans) {
        const t = (s.innerText || '').trim();
        if (t.length > best.length && t.length < 2200) best = t;
      }
      return best;
    }
    """
    try:
        text = (page.evaluate(js) or "").strip()
    except Exception:  # noqa: BLE001
        text = ""
    if text:
        return text[:2000]
    return f"Instagram Reel {code}" if code else "Instagram Reel"


def _first_visible(page: Page, selectors: list[str]) -> Locator | None:
    for sel in selectors:
        loc = page.locator(sel)
        try:
            n = loc.count()
        except Exception:  # noqa: BLE001
            continue
        for i in range(min(n, 8)):
            el = loc.nth(i)
            try:
                if el.is_visible():
                    return el
            except Exception:  # noqa: BLE001
                continue
    return None


def _aria_selectors(labels: list[str]) -> list[str]:
    sels = []
    for lab in labels:
        esc = lab.replace('"', '\\"')
        sels.append(f'svg[aria-label="{esc}"]')
        sels.append(f'[aria-label="{esc}"]')
    return sels


def find_like(page: Page, cfg: Config) -> Locator | None:
    return _first_visible(page, _aria_selectors(cfg.like_labels))


def already_liked(page: Page, cfg: Config) -> bool:
    return _first_visible(page, _aria_selectors(cfg.unlike_labels)) is not None


def find_comment(page: Page, cfg: Config) -> Locator | None:
    return _first_visible(page, _aria_selectors(cfg.comment_labels))


def find_follow(page: Page, cfg: Config) -> Locator | None:
    for name in cfg.follow_names:
        try:
            el = page.get_by_role("button", name=name, exact=True)
            n = el.count()
            for i in range(min(n, 6)):
                cand = el.nth(i)
                if cand.is_visible():
                    return cand
        except Exception:  # noqa: BLE001
            continue
    return None


def scroll_next(page: Page) -> None:
    """Advance to the next reel with a slightly varied gesture."""
    size = page.viewport_size or {"width": 1280, "height": 800}
    delta = int(size["height"] * random.uniform(0.85, 1.05))
    try:
        page.mouse.move(size["width"] / 2, size["height"] / 2)
        page.mouse.wheel(0, delta)
    except Exception:  # noqa: BLE001
        try:
            page.keyboard.press("ArrowDown")
        except Exception:  # noqa: BLE001
            pass
