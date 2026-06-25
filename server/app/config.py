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

    # Reels parser-bot launched from the UI. parser_dir empty = auto-detect
    # (<repo>/parser); parser_server_url is the URL the bot uploads back to.
    parser_dir: str = ""
    parser_server_url: str = "http://localhost:8000"
    parser_max_reels: int = 30
    # Browser the bot attaches to over CDP. The "Start Feed Parsing" button
    # launches Chrome with remote debugging if it isn't already reachable.
    parser_chrome_path: str = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    parser_cdp_port: int = 9222
    parser_chrome_profile_dir: str = ""  # empty = <parser_dir>/state/chrome-profile
    # Folder scanned for code-backed checker plugins (see app.pipelines.plugins).
    # Empty = auto-detect (<server>/plugins).
    pipeline_plugins_dir: str = ""
    # Default per-scanner scam threshold: a reel is scam when any checker's
    # confidence reaches its threshold. Editable live on the Pipeline tab.
    scam_threshold: float = 0.5
    # Auto-investigate: when a reel is flagged scam (any checker >= threshold),
    # automatically scan its whole channel (up to max). Toggled live from the UI.
    auto_scan_enabled: bool = False
    auto_scan_max_reels: int = 20
    # Per-checker scam thresholds (any one reaching its value triggers a scan).
    auto_scan_threshold_semantic: float = 0.7
    auto_scan_threshold_ocr: float = 0.7
    auto_scan_threshold_clip: float = 0.7
    auto_scan_threshold_audio: float = 0.7

    @property
    def enabled_pipeline_list(self) -> list[str]:
        return [name.strip() for name in self.enabled_pipelines.split(",") if name.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
