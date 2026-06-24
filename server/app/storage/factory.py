from __future__ import annotations

from app.config import Settings
from app.storage.base import BlobStorage
from app.storage.local import LocalStorage


def build_storage(settings: Settings) -> BlobStorage:
    backend = settings.storage_backend
    if backend == "local":
        return LocalStorage(settings.storage_dir)
    raise ValueError(f"unknown storage backend: {backend!r}")
