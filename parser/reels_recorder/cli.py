"""CLI args + tunable configuration (selectors and timings live here)."""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field


# --- Selectors (EN + RU labels). Instagram localizes aria-labels, so keep both. ---
LIKE_LABELS = ["Like", "Нравится"]
UNLIKE_LABELS = ["Unlike", 'Убрать отметку «Нравится»', "Убрать отметку"]
COMMENT_LABELS = ["Comment", "Комментировать", "Комментарии"]
FOLLOW_NAMES = ["Follow", "Подписаться"]
LOGIN_MARKERS = [
    'input[name="username"]',
    'input[name="password"]',
]

REELS_URL = "https://www.instagram.com/reels/"


@dataclass
class Config:
    debug: bool = False
    cdp_url: str = "http://127.0.0.1:9222"  # 127.0.0.1, not localhost (Chrome CDP is IPv4-only)
    server_url: str = "http://localhost:8000"
    out_dir: str = "recordings"
    state_dir: str = "state"
    max_reels: int | None = None

    # Timings (seconds)
    max_dwell: float = 60.0          # idle watchdog: never stay on one reel longer
    comment_dwell: tuple = (2.0, 5.0)
    inter_reel_delay: tuple = (0.8, 3.0)
    base_watch: tuple = (6.0, 22.0)  # fallback watch window when duration is unknown
    poll_step: float = 0.4

    # Behaviour probabilities
    skip_early_prob: float = 0.40
    skip_fraction: tuple = (0.2, 0.7)
    comment_prob: float = 0.20
    follow_prob: float = 0.05

    like_labels: list = field(default_factory=lambda: LIKE_LABELS)
    unlike_labels: list = field(default_factory=lambda: UNLIKE_LABELS)
    comment_labels: list = field(default_factory=lambda: COMMENT_LABELS)
    follow_names: list = field(default_factory=lambda: FOLLOW_NAMES)


def parse_args(argv: list[str] | None = None) -> Config:
    p = argparse.ArgumentParser(
        prog="reels_recorder",
        description="Record Instagram Reels via an anti-detect browser and upload them.",
    )
    p.add_argument("--debug", action="store_true",
                   help="Pretend to upload (no HTTP) and assume server returns True for all actions.")
    p.add_argument("--cdp-url", default=Config.cdp_url,
                   help="CDP endpoint of the already-running anti-detect browser (use 127.0.0.1, not localhost).")
    p.add_argument("--server-url", default=Config.server_url,
                   help="AI Media Watch backend base URL.")
    p.add_argument("--out", dest="out_dir", default=Config.out_dir,
                   help="Directory for saved .webm clips.")
    p.add_argument("--max-reels", type=int, default=None,
                   help="Stop after recording this many new reels (for testing).")
    a = p.parse_args(argv)
    return Config(
        debug=a.debug,
        cdp_url=a.cdp_url,
        server_url=a.server_url,
        out_dir=a.out_dir,
        max_reels=a.max_reels,
    )
