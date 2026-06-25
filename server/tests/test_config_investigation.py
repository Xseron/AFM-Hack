from __future__ import annotations

from app.config import Settings


def test_investigation_defaults():
    s = Settings(_env_file=None)
    assert s.investigator_url == "http://localhost:8010"
    assert s.telegram_url == "http://localhost:8020"
    assert s.httpx_timeout_seconds == 5.0


def test_investigation_env_override(monkeypatch):
    monkeypatch.setenv("MW_INVESTIGATOR_URL", "http://inv:9000")
    s = Settings(_env_file=None)
    assert s.investigator_url == "http://inv:9000"
