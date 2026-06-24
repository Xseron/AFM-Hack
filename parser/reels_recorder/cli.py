"""CLI args + tunable configuration (selectors and timings live here)."""
from __future__ import annotations

import argparse
import os
from dataclasses import dataclass, field
from pathlib import Path


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
    # When set, parse reels from this profile/channel instead of the global feed.
    channel_url: str = ""
    instagram_username: str = ""
    instagram_password: str = ""
    auto_login: bool = False

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


def load_env(path: str = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str) -> int | None:
    value = os.getenv(name)
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def parse_args(argv: list[str] | None = None) -> Config:
    load_env()
    p = argparse.ArgumentParser(
        prog="reels_recorder",
        description="Record Instagram Reels via an anti-detect browser and upload them.",
    )
    p.add_argument("--debug", action="store_true", default=_env_bool("REELS_DEBUG"),
                   help="Pretend to upload (no HTTP) and assume server returns True for all actions.")
    p.add_argument("--cdp-url", default=os.getenv("REELS_CDP_URL", Config.cdp_url),
                   help="CDP endpoint of the already-running anti-detect browser (use 127.0.0.1, not localhost).")
    p.add_argument("--server-url", default=os.getenv("REELS_SERVER_URL", Config.server_url),
                   help="AI Media Watch backend base URL.")
    p.add_argument("--out", dest="out_dir", default=os.getenv("REELS_OUT_DIR", Config.out_dir),
                   help="Directory for saved .webm clips.")
    p.add_argument("--max-reels", type=int, default=_env_int("REELS_MAX_REELS"),
                   help="Stop after recording this many new reels (for testing).")
    p.add_argument("--channel", dest="channel_url", default=os.getenv("REELS_CHANNEL", ""),
                   help="Parse reels from this profile/channel URL instead of the global feed.")
    p.add_argument("--auto-login", action="store_true", default=_env_bool("INSTAGRAM_AUTO_LOGIN"),
                   help="Try to log in using INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD from .env.")
    a = p.parse_args(argv)
    return Config(
        debug=a.debug,
        cdp_url=a.cdp_url,
        server_url=a.server_url,
        out_dir=a.out_dir,
        max_reels=a.max_reels,
        channel_url=a.channel_url.strip(),
        instagram_username=os.getenv("INSTAGRAM_USERNAME", ""),
        instagram_password=os.getenv("INSTAGRAM_PASSWORD", ""),
        auto_login=a.auto_login,
    )
