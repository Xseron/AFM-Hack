"""Cross-run dedup of recorded reels by shortcode."""
from __future__ import annotations

import json
import os

from .cli import Config


class SeenStore:
    def __init__(self, cfg: Config):
        self.path = os.path.join(cfg.state_dir, f"seen_{cfg.platform}.json")
        self._seen: set[str] = set()
        self._load()

    def _load(self) -> None:
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                self._seen = set(json.load(f))
        except Exception:  # noqa: BLE001
            self._seen = set()

    def has(self, code: str) -> bool:
        return code in self._seen

    def add(self, code: str) -> None:
        self._seen.add(code)
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(sorted(self._seen), f)
        except Exception as e:  # noqa: BLE001
            print(f"[warn] could not persist seen_reels: {e}")
