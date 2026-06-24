from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_components

router = APIRouter()


@router.post("/dedup/clear")
async def clear_dedup(components=Depends(get_components)) -> dict:
    cleared = await components.repo.clear_content_hashes()
    return {"cleared": cleared}
