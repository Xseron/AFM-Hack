from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_components
from app.api.serializers import job_list_item

router = APIRouter()


@router.get("/review-queue")
async def review_queue(limit: int = 50, components=Depends(get_components)) -> dict:
    jobs = await components.repo.review_queue(limit=limit)
    return {
        "items": [job_list_item(j) for j in jobs]
    }


@router.get("/priority-list")
async def priority_list(limit: int = 50, components=Depends(get_components)) -> dict:
    jobs = await components.repo.priority_queue(limit=limit)
    return {
        "items": [job_list_item(j) for j in jobs]
    }


@router.get("/recent-jobs")
async def recent_jobs(limit: int = 50, components=Depends(get_components)) -> dict:
    jobs = await components.repo.recent_jobs(limit=limit)
    return {
        "items": [job_list_item(j) for j in jobs]
    }
