from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_components

router = APIRouter()


@router.get("/pipelines")
async def list_pipelines(components=Depends(get_components)) -> dict:
    return {
        "pipelines": [
            {"name": p.name, "modality": p.modality} for p in components.registry.all()
        ]
    }
