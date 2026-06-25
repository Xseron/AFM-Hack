"""Talks to the AI Media Watch backend. Debug mode pretends + assumes True."""
from __future__ import annotations

import json

import requests

from .cli import Config


class ServerClient:
    def __init__(self, cfg: Config):
        self.cfg = cfg

    def upload(self, video: bytes, description: str, meta: dict) -> dict:
        kb = len(video) / 1024.0
        code = meta.get("shortcode", "?")
        if self.cfg.debug:
            print(f"[debug] pretend sent: {code} ({kb:.0f} KB)")
            return {"job_id": "debug", "duplicate": False, "near_duplicates": []}

        url = self.cfg.server_url.rstrip("/") + "/videos"
        files = {"video": (f"{self.cfg.platform}_{code}.webm", video, "video/webm")}
        data = {
            "description": description,
            "source_platform": self.cfg.platform,
            "source_url": meta.get("source_url", ""),
            "source_meta": json.dumps(meta, ensure_ascii=False),
        }
        try:
            r = requests.post(url, files=files, data=data, timeout=120)
            r.raise_for_status()
        except Exception as e:  # noqa: BLE001
            print(f"[warn] upload failed for {code}: {e}")
            return {}
        print(f"[sent] {code} ({kb:.0f} KB)")
        try:
            return r.json()
        except Exception:  # noqa: BLE001
            return {}

    def get_decisions(self, meta: dict) -> dict:
        """{like, comment, follow}. Debug -> all True; normal -> safe stub (all False).

        This is the single seam to wire a real decision endpoint to later.
        """
        if self.cfg.debug:
            return {"like": True, "comment": True, "follow": True}
        return {"like": False, "comment": False, "follow": False}
