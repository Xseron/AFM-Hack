"""Start/stop the reels parser-bot against a given Instagram channel."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import get_components

router = APIRouter(prefix="/parser")


class StartRequest(BaseModel):
    channel_url: str
    max_reels: int | None = None


class ReelRequest(BaseModel):
    reel_url: str


class FeedRequest(BaseModel):
    max_reels: int | None = None


class AutoScanRequest(BaseModel):
    enabled: bool | None = None
    thresholds: dict[str, float] | None = None
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


@router.post("/feed")
def start_feed(body: FeedRequest, components=Depends(get_components)) -> dict:
    # sync def: launching Chrome can block ~20s, so run it off the event loop.
    max_reels = body.max_reels if (body.max_reels and body.max_reels > 0) else None
    try:
        return components.parser.start_feed(max_reels=max_reels)
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@router.post("/reel")
async def check_reel(body: ReelRequest, components=Depends(get_components)) -> dict:
    url = (body.reel_url or "").strip()
    if "/reel" not in url:
        raise HTTPException(status_code=422, detail="expected an Instagram reel URL")
    try:
        return components.parser.start_reel(url)
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.post("/stop")
async def stop_parser(components=Depends(get_components)) -> dict:
    return components.parser.stop()


@router.get("/status")
def parser_status(components=Depends(get_components)) -> dict:
    # sync def: status() probes the CDP port, so keep it off the event loop.
    return components.parser.status()


@router.get("/auto-scan")
async def get_auto_scan(components=Depends(get_components)) -> dict:
    return components.auto_scan.as_dict()


@router.post("/auto-scan")
async def set_auto_scan(body: AutoScanRequest, components=Depends(get_components)) -> dict:
    state = components.auto_scan
    if body.enabled is not None:
        state.enabled = body.enabled
    if body.thresholds:
        for checker, value in body.thresholds.items():
            if checker in state.thresholds:
                state.thresholds[checker] = max(0.0, min(1.0, float(value)))
    if body.max_reels is not None and body.max_reels > 0:
        state.max_reels = body.max_reels
    return state.as_dict()
