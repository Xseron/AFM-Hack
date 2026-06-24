"""Start/stop the reels parser-bot against a given Instagram channel."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import get_components

router = APIRouter(prefix="/parser")


class StartRequest(BaseModel):
    channel_url: str
    max_reels: int | None = None


@router.post("/start")
async def start_parser(body: StartRequest, components=Depends(get_components)) -> dict:
    url = (body.channel_url or "").strip()
    if not url:
        raise HTTPException(status_code=422, detail="channel_url must not be empty")
    if "instagram.com" not in url and not url.lstrip("@").replace(".", "").replace("_", "").isalnum():
        raise HTTPException(status_code=422, detail="expected an Instagram profile URL or handle")
    max_reels = body.max_reels or components.settings.parser_max_reels
    try:
        return components.parser.start(url, max_reels=max_reels)
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.post("/stop")
async def stop_parser(components=Depends(get_components)) -> dict:
    return components.parser.stop()


@router.get("/status")
async def parser_status(components=Depends(get_components)) -> dict:
    return components.parser.status()
