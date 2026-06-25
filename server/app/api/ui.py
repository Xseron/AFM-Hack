from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse, RedirectResponse

from app.api.deps import get_components

router = APIRouter()

_INDEX = Path(__file__).parent.parent / "static" / "index.html"


@router.get("/")
async def index() -> FileResponse:
    return FileResponse(_INDEX)


@router.get("/architecture-ui")
async def architecture_ui() -> RedirectResponse:
    return RedirectResponse(url="/#/pipeline")


@router.get("/models")
async def models(components=Depends(get_components)) -> dict:
    loaded = components.models.available() if components.models is not None else {}
    return {
        "models_enabled": components.settings.models_enabled,
        "model_device": components.settings.model_device,
        "devices": components.models.devices() if components.models is not None else {},
        "allow_model_downloads": components.settings.allow_model_downloads,
        "embedding_backend": components.settings.embedding_backend,
        "available": loaded,
    }
