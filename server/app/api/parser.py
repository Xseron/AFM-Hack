"""Start/stop the reels parser-bot against a given Instagram channel."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import get_components

router = APIRouter(prefix="/parser")


class StartRequest(BaseModel):
    channel_url: str
    max_reels: int | None = None
    platform: str = "instagram"
    max_video_seconds: float | None = None


class ReelRequest(BaseModel):
    reel_url: str
    platform: str = "instagram"
    max_video_seconds: float | None = None


class FeedRequest(BaseModel):
    max_reels: int | None = None
    platform: str = "instagram"
    max_video_seconds: float | None = None


def _max_video_seconds(settings, platform: str, override: float | None) -> float | None:
    """Per-platform recording cap: request override wins, else the platform's setting."""
    if override is not None and override > 0:
        return override
    value = (
        settings.parser_max_video_seconds_tiktok
        if platform == "tiktok"
        else settings.parser_max_video_seconds_instagram
    )
    return value if value and value > 0 else None


class AutoScanRequest(BaseModel):
    enabled: bool | None = None
    thresholds: dict[str, float] | None = None
    max_reels: int | None = None


@router.post("/start")
async def start_parser(body: StartRequest, components=Depends(get_components)) -> dict:
    url = (body.channel_url or "").strip()
    platform = _platform(body.platform, url)
    if not url:
        raise HTTPException(status_code=422, detail="channel_url must not be empty")
    if platform == "instagram":
        ok_handle = url.lstrip("@").replace(".", "").replace("_", "").isalnum()
        if "instagram.com" not in url and not ok_handle:
            raise HTTPException(status_code=422, detail="expected an Instagram profile URL or handle")
    elif platform == "tiktok":
        ok_handle = url.lstrip("@").replace(".", "").replace("_", "").replace("-", "").isalnum()
        if "tiktok.com" not in url and not ok_handle:
            raise HTTPException(status_code=422, detail="expected a TikTok profile URL or handle")
    max_reels = body.max_reels or components.settings.parser_max_reels
    cap = _max_video_seconds(components.settings, platform, body.max_video_seconds)
    try:
        return components.parser.start(url, max_reels=max_reels, platform=platform, max_video_seconds=cap)
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.post("/feed")
def start_feed(body: FeedRequest, components=Depends(get_components)) -> dict:
    # sync def: launching Chrome can block ~20s, so run it off the event loop.
    max_reels = body.max_reels if (body.max_reels and body.max_reels > 0) else None
    platform = _platform(body.platform)
    cap = _max_video_seconds(components.settings, platform, body.max_video_seconds)
    try:
        return components.parser.start_feed(max_reels=max_reels, platform=platform, max_video_seconds=cap)
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.post("/reel")
async def check_reel(body: ReelRequest, components=Depends(get_components)) -> dict:
    url = (body.reel_url or "").strip()
    platform = _platform(body.platform, url)
    if platform == "instagram" and "/reel" not in url:
        raise HTTPException(status_code=422, detail="expected an Instagram reel URL")
    if platform == "tiktok" and "/video/" not in url:
        raise HTTPException(status_code=422, detail="expected a TikTok video URL")
    cap = _max_video_seconds(components.settings, platform, body.max_video_seconds)
    try:
        return components.parser.start_reel(url, platform=platform, max_video_seconds=cap)
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


def _platform(value: str, source: str = "") -> str:
    raw = (value or "").strip().lower()
    blob = f"{raw} {source or ''}".lower()
    if "tiktok.com" in blob or raw == "tiktok":
        return "tiktok"
    if "instagram.com" in blob or raw in ("", "instagram"):
        return "instagram"
    raise HTTPException(status_code=422, detail=f"unsupported parser platform: {value}")
