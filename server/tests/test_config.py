from app.config import Settings, get_settings


def test_defaults():
    s = Settings()
    assert s.queue_backend == "memory"
    assert s.database_url.startswith("sqlite+aiosqlite")
    assert s.storage_dir
    assert s.max_upload_bytes > 0


def test_env_override(monkeypatch):
    monkeypatch.setenv("MW_QUEUE_BACKEND", "redis")
    assert Settings().queue_backend == "redis"


def test_get_settings_cached():
    assert get_settings() is get_settings()
