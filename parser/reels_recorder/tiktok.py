"""Locate and scroll TikTok short videos in the web feed/profile UI."""
from __future__ import annotations

import random
import re

from playwright.sync_api import Page

TIKTOK_FEED_URL = "https://www.tiktok.com/foryou"
_VIDEO_RE = re.compile(r"(?:tiktok\.com)?/@([A-Za-z0-9._-]+)/video/(\d+)|/video/(\d+)")


_ACTIVE_VIDEO_JS = r"""
  const visArea = (el) => {
    const r = el.getBoundingClientRect();
    const w = Math.min(r.right, innerWidth) - Math.max(r.left, 0);
    const h = Math.min(r.bottom, innerHeight) - Math.max(r.top, 0);
    return Math.max(0, w) * Math.max(0, h);
  };
  const vids = Array.from(document.querySelectorAll('video'));
  if (!vids.length) return null;
  const v = vids.slice().sort((a, b) => visArea(b) - visArea(a))[0];
  let el = v, container = v;
  for (let i = 0; i < 12 && el && el.parentElement; i++) {
    el = el.parentElement;
    container = el;
    const attr = `${el.getAttribute('data-e2e') || ''} ${el.getAttribute('data-testid') || ''}`;
    if (/video|feed|item|browse/i.test(attr) && el.querySelectorAll('video').length === 1) break;
    if (el.querySelectorAll('video').length > 1) {
      container = v.parentElement || v;
      break;
    }
  }
"""


def code_from_url(url: str) -> str | None:
    m = _VIDEO_RE.search(url or "")
    if not m:
        return None
    return m.group(2) or m.group(3)


def _handle_from_url(url: str) -> str:
    m = _VIDEO_RE.search(url or "")
    return (m.group(1) or "").lower() if m else ""


def video_url(code: str, handle: str = "") -> str:
    handle = (handle or "").strip().lstrip("@")
    if handle:
        return f"https://www.tiktok.com/@{handle}/video/{code}"
    return f"https://www.tiktok.com/video/{code}"


def shortcode(page: Page) -> str | None:
    code = code_from_url(page.url or "")
    if code:
        return code
    js = r"""
    () => {
      const root = document.querySelector('main') || document.body;
      for (const a of root.querySelectorAll('a[href*="/video/"]')) {
        const m = (a.href || a.getAttribute('href') || '').match(/\/video\/(\d+)/);
        if (m) return m[1];
      }
      const visArea = (v) => {
        const r = v.getBoundingClientRect();
        const w = Math.max(0, Math.min(r.right, innerWidth) - Math.max(r.left, 0));
        const h = Math.max(0, Math.min(r.bottom, innerHeight) - Math.max(r.top, 0));
        return w * h;
      };
      const v = Array.from(document.querySelectorAll('video'))
        .sort((a, b) => visArea(b) - visArea(a))
        .find(x => x.currentSrc || x.src);
      if (v) {
        const src = v.currentSrc || v.src || '';
        let m = src.match(/(?:vid|video)[=/]([A-Za-z0-9_-]{8,})/);
        if (m) return m[1];
        m = src.match(/blob:https?:\/\/[^/]+\/([A-Za-z0-9-]{8,})/);
        if (m) return m[1];
      }
      return '';
    }
    """
    try:
        return (page.evaluate(js) or "").strip() or None
    except Exception:  # noqa: BLE001
        return None


_CAPTION_JS = r"""
() => {
""" + _ACTIVE_VIDEO_JS + r"""
  const clean = (s) => (s || '').replace(/\s+/g, ' ').trim();
  const noise = /^(follow|following|friends|for you|live|photo|likes?|comments?|shares?|save|report|not interested|log in|sign up)$/i;
  const roots = [container, document.querySelector('main'), document.body].filter(Boolean);
  const selectors = [
    '[data-e2e="video-desc"]',
    '[data-e2e="browse-video-desc"]',
    '[data-testid*="video-desc"]',
    'h1',
    'strong',
    'span'
  ];
  let best = '';
  for (const root of roots) {
    for (const sel of selectors) {
      for (const el of root.querySelectorAll(sel)) {
        if (el.closest('nav')) continue;
        const t = clean(el.innerText || el.textContent);
        if (!t || t.length < 2 || noise.test(t)) continue;
        if (/^[\d\s.,KMБМ]+$/.test(t)) continue;
        if (t.length > best.length) best = t;
      }
      if (best && sel.includes('video-desc')) return best.slice(0, 2000);
    }
  }
  return best.slice(0, 2000);
}
"""


def caption(page: Page, code: str | None) -> str:
    try:
        text = (page.evaluate(_CAPTION_JS) or "").strip()
    except Exception:  # noqa: BLE001
        text = ""
    if text:
        return text[:2000]
    return f"TikTok video {code}" if code else "TikTok video"


_AUTHOR_JS = r"""
() => {
""" + _ACTIVE_VIDEO_JS + r"""
  const handleOf = (href) => {
    const m = (href || '').match(/\/@([A-Za-z0-9._-]+)/);
    return m ? m[1] : '';
  };
  let el = container;
  for (let i = 0; i < 10 && el; i++, el = el.parentElement) {
    for (const a of el.querySelectorAll('a[href*="/@"]')) {
      const h = handleOf(a.getAttribute('href') || a.href);
      if (h) return h;
    }
    const tagged = el.querySelector('[data-e2e*="author"], [data-testid*="author"]');
    if (tagged) {
      const t = (tagged.innerText || tagged.textContent || '').replace(/^@/, '').trim();
      if (t) return t.split(/\s+/)[0].replace(/^@/, '');
    }
  }
  for (const a of document.querySelectorAll('a[href*="/@"]')) {
    const h = handleOf(a.getAttribute('href') || a.href);
    if (h) return h;
  }
  return '';
}
"""


def author(page: Page) -> str:
    handle = _handle_from_url(page.url or "")
    if handle:
        return handle
    try:
        return (page.evaluate(_AUTHOR_JS) or "").strip().lstrip("@")
    except Exception:  # noqa: BLE001
        return ""


def channel_handle(url: str) -> str:
    u = (url or "").strip()
    m = re.search(r"tiktok\.com/@([A-Za-z0-9._-]+)", u)
    user = m.group(1) if m else u.strip("/@ ")
    return user.lower()


def channel_reels_url(url: str) -> str:
    return f"https://www.tiktok.com/@{channel_handle(url)}"


def channel_shortcodes(page: Page) -> list[str]:
    js = r"""
    () => {
      const root = document.querySelector('main') || document.body;
      const out = [], seen = new Set();
      for (const a of root.querySelectorAll('a[href*="/video/"]')) {
        const href = a.href || a.getAttribute('href') || '';
        const m = href.match(/\/video\/(\d+)/);
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
    try:
        page.evaluate("() => window.scrollBy(0, window.innerHeight * 0.85)")
    except Exception:  # noqa: BLE001
        try:
            page.keyboard.press("End")
        except Exception:  # noqa: BLE001
            pass


def scroll_next(page: Page) -> None:
    size = page.viewport_size or {"width": 1280, "height": 800}
    delta = int(size["height"] * random.uniform(0.85, 1.1))
    try:
        page.keyboard.press("ArrowDown")
        page.wait_for_timeout(250)
    except Exception:  # noqa: BLE001
        pass
    try:
        page.mouse.move(size["width"] / 2, size["height"] / 2)
        page.mouse.wheel(0, delta)
    except Exception:  # noqa: BLE001
        pass
