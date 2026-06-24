from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MW_", env_file=".env", extra="ignore")

    queue_backend: str = "memory"
    # Run triage+analysis workers as background tasks inside the API process.
    # Lets a single `uvicorn` process handle the whole pipeline (great for the
    # in-memory queue demo). For multi-machine scale use redis + separate workers.
    run_workers_inline: bool = False
    redis_url: str = "redis://localhost:6379/0"
    database_url: str = "sqlite+aiosqlite:///./media_watch.db"
    storage_backend: str = "local"
    storage_dir: str = "./buffer"
    max_upload_bytes: int = 500 * 1024 * 1024
    # Comma-separated pipeline names to enable; empty = all registered defaults.
    enabled_pipelines: str = ""

    # Real ML models (Whisper / CLIP / OCR+embedding). Off by default so the
    # skeleton/tests run without heavy deps; turn on for the real pipelines.
    models_enabled: bool = False
    model_device: str = "cpu"  # cpu | cuda
    allow_model_downloads: bool = False  # else load from local HF cache only
    whisper_model: str = "base"
    clip_model: str = "openai/clip-vit-base-patch32"
    embedding_backend: str = "hybrid"  # tfidf | sentence-transformers | hybrid
    ocr_backend: str = "rapidocr"  # auto | rapidocr | tesseract | easyocr
    transcripts_dir: str = "./output/transcripts"

    @property
    def enabled_pipeline_list(self) -> list[str]:
        return [name.strip() for name in self.enabled_pipelines.split(",") if name.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
