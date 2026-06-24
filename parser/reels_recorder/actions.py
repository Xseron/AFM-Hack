"""Human-like interactions: like, open/close comments, follow."""
from __future__ import annotations

import random

from playwright.sync_api import Page

from . import feed, humanize
from .cli import Config


def like(page: Page, cfg: Config) -> bool:
    if feed.already_liked(page, cfg):
        return False
    btn = feed.find_like(page, cfg)
    if btn is None:
        print("[warn] like button not found")
        return False
    try:
        btn.click(timeout=3000)
        return True
    except Exception as e:  # noqa: BLE001
        print(f"[warn] like click failed: {e}")
        return False


def open_comments_then_close(page: Page, cfg: Config) -> bool:
    btn = feed.find_comment(page, cfg)
    if btn is None:
        print("[warn] comment button not found")
        return False
    try:
        btn.click(timeout=3000)
    except Exception as e:  # noqa: BLE001
        print(f"[warn] open comments failed: {e}")
        return False

    humanize.sleep_range(cfg.comment_dwell)  # read comments 2-5s
    _close_comments(page)
    return True


def _close_comments(page: Page) -> None:
    """Close comments by tapping the upper part of the screen; Escape as fallback."""
    size = page.viewport_size or {"width": 1280, "height": 800}
    try:
        page.mouse.click(size["width"] / 2, random.uniform(6, 20))
    except Exception:  # noqa: BLE001
        pass
    try:
        page.keyboard.press("Escape")
    except Exception:  # noqa: BLE001
        pass


def follow(page: Page, cfg: Config) -> bool:
    btn = feed.find_follow(page, cfg)
    if btn is None:
        return False  # already following or no button — not an error
    try:
        btn.click(timeout=3000)
        return True
    except Exception as e:  # noqa: BLE001
        print(f"[warn] follow click failed: {e}")
        return False
