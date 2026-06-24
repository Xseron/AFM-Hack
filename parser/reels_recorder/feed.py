"""Locate the active reel: shortcode (dedup key), caption, action buttons, scrolling."""
from __future__ import annotations

import random
import re

from playwright.sync_api import Locator, Page

from .cli import Config

# Feed URLs are /reels/<code>/ (plural); permalinks are /reel/<code>/ (singular).
_SHORTCODE_RE = re.compile(r"/reels?/([A-Za-z0-9_-]+)")

# The reels feed stacks every reel in the DOM with no <article> wrapper, so we
# scope to the *active* reel only: take the most-visible <video>, then climb to
# the nearest ancestor that still contains a single video (the per-reel block).
_ACTIVE_REEL_JS = r"""
  const visArea = (el) => { const r = el.getBoundingClientRect();
    const w = Math.min(r.right, innerWidth) - Math.max(r.left, 0);
    const h = Math.min(r.bottom, innerHeight) - Math.max(r.top, 0);
    return Math.max(0, w) * Math.max(0, h); };
  const vids = Array.from(document.querySelectorAll('video'));
  if (!vids.length) return null;
  const v = vids.slice().sort((a, b) => visArea(b) - visArea(a))[0];
  let el = v, container = v;
  while (el && el.parentElement) {
    el = el.parentElement;
    if (el.querySelectorAll('video').length > 1) break;
    container = el;
  }
"""


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
    """Best-effort caption text for the upload description (server needs it non-empty).

    Scoped to the *active* reel (see _ACTIVE_REEL_JS). Within that reel we take the
    longest "leaf" text span, skipping the things that are not the caption: the
    author username, the audio attribution ("artist · track"), view/like counts,
    and UI words ("ещё", "Подробнее", "Реклама", …). This avoids the old bug where
    the longest text on the page won — which on sponsored reels was an ad
    disclaimer and on others a location tag or the whole-reel wrapper text.
    """
    expand_caption(page)
    try:
        text = (page.evaluate(_CAPTION_JS) or "").strip()
    except Exception:  # noqa: BLE001
        text = ""
    if text:
        return text[:2000]
    return f"Instagram Reel {code}" if code else "Instagram Reel"


_CAPTION_JS = r"""
() => {
  const clean = (s) => (s || '').replace(/\s+/g, ' ').trim();
  const NOISE = /^(…\s*)?(more|ещё|еще|меньше|less|подробнее|реклама|sponsored|follow|подписаться|original audio|оригинальный звук|verified|подтверждённый)$/i;
""" + _ACTIVE_REEL_JS + r"""
  const usable = (t) => {
    if (!t || t.length < 2) return false;
    if (NOISE.test(t)) return false;
    if (/^[\d\s.,]+$/.test(t)) return false;   // view / like counts
    if (/\s·\s/.test(t)) return false;          // audio attribution "artist · track"
    return true;
  };
  // The caption span owns its text directly; hashtag/mention <a> children are
  // short, so a child carrying a big chunk of text means this is a wrapper.
  let best = '';
  for (const s of container.querySelectorAll('span, h1')) {
    let childMax = 0;
    for (const c of s.children) { const ct = clean(c.innerText); if (ct.length > childMax) childMax = ct.length; }
    if (childMax > 40) continue;
    const t = clean(s.innerText);
    if (usable(t) && t.length > best.length) best = t;
  }
  // Strip a trailing inline expander that stuck to the text ("… ещё" / "меньше").
  best = best.replace(/\s*…\s*(ещё|еще|more)\s*$/i, '').replace(/\s*(ещё|еще|меньше)\s*$/i, '').trim();
  return best.slice(0, 2000);
}
"""


# Clicks the active reel's inline caption expander ("… ещё" / "more"). It is a
# plain pointer span, not a link — we skip anchors so we never trigger a
# sponsored reel's "Подробнее" CTA (which navigates away).
_EXPAND_JS = r"""
() => {
""" + _ACTIVE_REEL_JS + r"""
  for (const e of container.querySelectorAll('span, div[role="button"], button')) {
    const t = (e.innerText || '').replace(/\s+/g, ' ').trim();
    if (/^(…\s*)?(ещё|еще|more)$/i.test(t) && !e.closest('a')) {
      try { e.click(); return true; } catch (_) {}
    }
  }
  return false;
}
"""


def expand_caption(page: Page) -> None:
    """Click the active reel's inline "more/ещё" caption expander if present."""
    try:
        if page.evaluate(_EXPAND_JS):
            page.wait_for_timeout(300)
    except Exception:  # noqa: BLE001
        pass


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


def channel_reels_url(url: str) -> str:
    """Normalize any profile/channel link into its Reels tab URL."""
    u = (url or "").strip()
    m = re.search(r"instagram\.com/([A-Za-z0-9._]+)", u)
    user = m.group(1) if m else u.strip("/@ ")
    return f"https://www.instagram.com/{user}/reels/"


def channel_shortcodes(page: Page) -> list[str]:
    """Reel shortcodes currently present in the profile's Reels grid, in order."""
    js = """
    () => {
      const out = [], seen = new Set();
      for (const a of document.querySelectorAll('a[href]')) {
        const m = (a.getAttribute('href') || '').match(/\\/reel\\/([A-Za-z0-9_-]+)/);
        if (m && !seen.has(m[1])) { seen.add(m[1]); out.push(m[1]); }
      }
      return out;
    }
    """
    try:
        return list(page.evaluate(js) or [])
    except Exception:  # noqa: BLE001
        return []


def scroll_window(page: Page) -> None:
    """Scroll the page (the profile grid) down to lazy-load more reels."""
    try:
        page.evaluate("() => window.scrollBy(0, window.innerHeight * 0.9)")
    except Exception:  # noqa: BLE001
        try:
            page.keyboard.press("End")
        except Exception:  # noqa: BLE001
            pass


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
