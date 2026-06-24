from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_components

router = APIRouter()


@router.get("/review-queue")
async def review_queue(limit: int = 50, components=Depends(get_components)) -> dict:
    jobs = await components.repo.review_queue(limit=limit)
    return {
        "items": [
            {
                "job_id": j.id,
                "status": j.status,
                "risk_score": j.risk_score,
                "priority": j.priority,
                "category": j.category,
            }
            for j in jobs
        ]
    }
