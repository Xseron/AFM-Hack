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
from pathlib import Path


def _default_parser_dir() -> str:
    # server/app/parser_control.py -> parents[2] == repo root
    return str(Path(__file__).resolve().parents[2] / "parser")


class ParserController:
    def __init__(self, parser_dir: str = "", server_url: str = "http://localhost:8000"):
        self._parser_dir = parser_dir or _default_parser_dir()
        self._server_url = server_url
        self._lock = threading.Lock()
        self._proc: subprocess.Popen | None = None
        self._channel: str = ""
        self._started_at: float | None = None
        self._log_path = str(Path(self._parser_dir) / "parser_run.log")

    def start(self, channel_url: str, max_reels: int | None = None) -> dict:
        channel_url = (channel_url or "").strip()
        if not channel_url:
            raise ValueError("channel_url must not be empty")
        with self._lock:
            if self._is_running():
                raise RuntimeError("parser is already running; stop it first")

            cmd = [
                sys.executable, "-u", "-m", "reels_recorder",
                "--channel", channel_url,
                "--server-url", self._server_url,
            ]
            if max_reels:
                cmd += ["--max-reels", str(max_reels)]

            log = open(self._log_path, "ab", buffering=0)
            log.write(f"\n=== start {channel_url} @ {time.ctime()} ===\n".encode("utf-8"))
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
            self._channel = channel_url
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

    def status(self) -> dict:
        running = self._is_running()
        return {
            "running": running,
            "channel": self._channel if running else "",
            "pid": self._proc.pid if (running and self._proc) else None,
            "started_at": self._started_at if running else None,
            "log_path": self._log_path,
        }

    # --- internals ---
    def _is_running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

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
