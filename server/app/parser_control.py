"""Launch and stop the reels parser-bot as a subprocess from the server.

The parser is a separate package under ``<repo>/parser``. It attaches to an
already-running anti-detect browser over CDP and uploads recorded reels back to
this server, so all we manage here is the OS process: start one channel parse at
a time and be able to stop it (killing the whole tree, incl. the Playwright
node driver).
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path


# The video checkers a reel is scored on; each gets its own scam threshold.
CHECKERS = ("semantic", "ocr", "clip", "audio")

# Where the bot looks for videos and which browser it attaches to over CDP.
PLATFORM_FEED_URLS = {
    "instagram": "https://www.instagram.com/reels/",
    "tiktok": "https://www.tiktok.com/foryou",
}
REELS_FEED_URL = PLATFORM_FEED_URLS["instagram"]
DEFAULT_CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PLATFORMS = tuple(PLATFORM_FEED_URLS)


@dataclass
class AutoScanState:
    """Runtime toggle: when enabled, a scam reel auto-triggers a full channel scan.

    A reel counts as scam when *any* checker's confidence reaches that checker's
    own threshold (each independently configurable from the UI).
    """
    enabled: bool = False
    thresholds: dict = field(default_factory=lambda: {c: 0.7 for c in CHECKERS})
    max_reels: int = 20           # cap per auto-triggered channel scan
    scanned: set = field(default_factory=set)  # channels already auto-scanned this run

    def as_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "thresholds": {c: self.thresholds.get(c, 1.0) for c in CHECKERS},
            "max_reels": self.max_reels,
            "scanned_count": len(self.scanned),
        }


def _default_parser_dir() -> str:
    # server/app/parser_control.py -> parents[2] == repo root
    return str(Path(__file__).resolve().parents[2] / "parser")


class ParserController:
    def __init__(
        self,
        parser_dir: str = "",
        server_url: str = "http://localhost:8000",
        chrome_path: str = "",
        cdp_port: int = 9222,
        chrome_profile_dir: str = "",
    ):
        self._parser_dir = parser_dir or _default_parser_dir()
        self._server_url = server_url
        self._chrome_path = chrome_path or DEFAULT_CHROME_PATH
        self._cdp_port = cdp_port
        self._chrome_profile_dir = chrome_profile_dir or str(
            Path(self._parser_dir) / "state" / "chrome-profile"
        )
        self._lock = threading.Lock()
        self._proc: subprocess.Popen | None = None
        self._browser_proc: subprocess.Popen | None = None
        self._channel: str = ""
        self._platform: str = "instagram"
        self._started_at: float | None = None
        self._log_path = str(Path(self._parser_dir) / "parser_run.log")

    def start(
        self,
        channel_url: str,
        max_reels: int | None = None,
        platform: str = "instagram",
        max_video_seconds: float | None = None,
    ) -> dict:
        channel_url = (channel_url or "").strip()
        if not channel_url:
            raise ValueError("channel_url must not be empty")
        platform = self._normalize_platform(platform)
        return self._spawn(
            ["--channel", channel_url], channel_url,
            max_reels=max_reels, platform=platform, max_video_seconds=max_video_seconds,
        )

    def start_reel(
        self, reel_url: str, platform: str = "instagram", max_video_seconds: float | None = None
    ) -> dict:
        reel_url = (reel_url or "").strip()
        if not reel_url:
            raise ValueError("reel_url must not be empty")
        platform = self._normalize_platform(platform, source=reel_url)
        return self._spawn(
            ["--reel", reel_url], reel_url, platform=platform, max_video_seconds=max_video_seconds
        )

    def start_feed(
        self,
        max_reels: int | None = None,
        platform: str = "instagram",
        max_video_seconds: float | None = None,
    ) -> dict:
        """Ensure the CDP browser is up, then record from the selected feed."""
        platform = self._normalize_platform(platform)
        browser = self.ensure_browser(platform=platform)
        status = self._spawn(
            [], f"{platform} feed",
            max_reels=max_reels, platform=platform, max_video_seconds=max_video_seconds,
        )
        status["browser_launched"] = browser.get("launched", False)
        return status

    # --- browser (CDP) ---
    def cdp_reachable(self) -> bool:
        url = f"http://127.0.0.1:{self._cdp_port}/json/version"
        try:
            with urllib.request.urlopen(url, timeout=0.5) as resp:  # noqa: S310 (localhost only)
                return resp.status == 200
        except Exception:  # noqa: BLE001
            return False

    def ensure_browser(self, platform: str = "instagram") -> dict:
        """Launch Chrome with remote debugging if it isn't already reachable."""
        platform = self._normalize_platform(platform)
        if self.cdp_reachable():
            return {"launched": False, "running": True}
        if not Path(self._chrome_path).exists():
            raise RuntimeError(
                f"Chrome not found at {self._chrome_path}; set MW_PARSER_CHROME_PATH"
            )
        Path(self._chrome_profile_dir).mkdir(parents=True, exist_ok=True)
        cmd = [
            self._chrome_path,
            f"--remote-debugging-port={self._cdp_port}",
            f"--user-data-dir={self._chrome_profile_dir}",
            PLATFORM_FEED_URLS[platform],
        ]
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
        self._browser_proc = subprocess.Popen(cmd, creationflags=creationflags)
        for _ in range(40):  # wait up to ~20s for CDP to come online
            if self.cdp_reachable():
                return {"launched": True, "running": True}
            time.sleep(0.5)
        raise RuntimeError(
            f"launched Chrome but its CDP endpoint never came up on port {self._cdp_port}"
        )

    def _spawn(
        self,
        mode_args: list[str],
        label: str,
        max_reels: int | None = None,
        platform: str = "instagram",
        max_video_seconds: float | None = None,
    ) -> dict:
        with self._lock:
            if self._is_running():
                raise RuntimeError("parser is already running; stop it first")
            platform = self._normalize_platform(platform, source=" ".join(mode_args))

            cmd = [sys.executable, "-u", "-m", "reels_recorder",
                   "--server-url", self._server_url, "--platform", platform, *mode_args]
            if max_reels:
                cmd += ["--max-reels", str(max_reels)]
            if max_video_seconds and max_video_seconds > 0:
                cmd += ["--max-video-seconds", str(max_video_seconds)]

            log = open(self._log_path, "ab", buffering=0)
            log.write(f"\n=== start {label} @ {time.ctime()} ===\n".encode("utf-8"))
            creationflags = 0
            preexec_fn = None
            if os.name == "nt":
                # New process group so we can kill the whole tree on stop.
                creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
            else:
                preexec_fn = os.setsid  # type: ignore[assignment]

            self._proc = subprocess.Popen(
                cmd,
                cwd=self._parser_dir,
                stdout=log,
                stderr=subprocess.STDOUT,
                creationflags=creationflags,
                preexec_fn=preexec_fn,
            )
            self._channel = label
            self._platform = platform
            self._started_at = time.time()
            return self.status()

    def stop(self) -> dict:
        with self._lock:
            proc = self._proc
            if proc is None or proc.poll() is not None:
                self._proc = None
                return {"stopped": False, "reason": "not running", **self.status()}
            self._kill_tree(proc)
            self._proc = None
            return {"stopped": True, **self.status()}

    def status(self, check_browser: bool = True) -> dict:
        running = self._is_running()
        return {
            "running": running,
            "channel": self._channel if running else "",
            "platform": self._platform if running else "",
            "pid": self._proc.pid if (running and self._proc) else None,
            "started_at": self._started_at if running else None,
            "browser_running": self.cdp_reachable() if check_browser else None,
            "log_path": self._log_path,
        }

    # --- internals ---
    def _is_running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def _normalize_platform(self, platform: str, source: str = "") -> str:
        value = (platform or "").strip().lower()
        blob = f"{value} {source or ''}".lower()
        if "tiktok.com" in blob or value == "tiktok":
            return "tiktok"
        if "instagram.com" in blob or value in ("", "instagram"):
            return "instagram"
        raise ValueError(f"unsupported parser platform: {platform}")

    def _kill_tree(self, proc: subprocess.Popen) -> None:
        try:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                    capture_output=True,
                )
            else:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
        except Exception:  # noqa: BLE001
            try:
                proc.kill()
            except Exception:  # noqa: BLE001
                pass
