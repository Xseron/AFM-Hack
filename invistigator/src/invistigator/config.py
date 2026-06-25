from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ig_username: str = ""
    ig_password: str = ""
    ig_2fa_secret: str = ""          # TOTP base32-ключ (генерит коды 2FA автоматически)
    ig_session_file: str = "invistigator_session"

    min_delay_sec: float = 8.0
    max_delay_sec: float = 20.0
    max_profiles_per_hour: int = 120

    http_proxy: str | None = None

    scraper_backend: str = "browser"   # "browser" (Playwright, безопаснее) | "api"
    browser_headless: bool = True

    crawler_url: str = "http://localhost:8000"

    csv_path: str = "results.csv"
    media_dir: str = "media"

    # OSINT-обогащение
    osint_enabled: bool = True
    osint_timeout_sec: int = 8
    username_search_platforms: str | None = None  # CSV-переопределение списка платформ
    jsonl_path: str = "results.jsonl"             # полные результаты (источник для графа)


@lru_cache
def get_settings() -> Settings:
    return Settings()
