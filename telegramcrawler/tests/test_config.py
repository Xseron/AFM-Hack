from aimw.config import Settings


def test_settings_reads_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_API_ID", "111")
    monkeypatch.setenv("TELEGRAM_API_HASH", "hash")
    monkeypatch.setenv("TELEGRAM_SESSION", "sess")
    monkeypatch.setenv("OPENROUTER_API_KEY", "key")
    monkeypatch.setenv("OPENROUTER_TEXT_MODEL", "text-model")
    monkeypatch.setenv("OPENROUTER_VISION_MODEL", "vision-model")
    s = Settings(_env_file=None)
    assert s.telegram_api_id == 111
    assert s.openrouter_text_model == "text-model"
    assert s.posts_per_channel == 50
    assert s.risk_review_threshold == 50
