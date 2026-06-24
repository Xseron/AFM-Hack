from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    telegram_api_id: int
    telegram_api_hash: str
    telegram_session: str
    openrouter_api_key: str
    openrouter_text_model: str
    openrouter_vision_model: str
    posts_per_channel: int = 50
    database_url: str = "sqlite:///aimw.db"
    risk_review_threshold: int = 50


@lru_cache
def get_settings() -> Settings:
    return Settings()
