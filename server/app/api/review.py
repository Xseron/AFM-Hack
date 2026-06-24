from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_components
from app.api.serializers import method_confidences

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
                "method_confidences": method_confidences(j.findings),
            }
            for j in jobs
        ]
    }


@router.get("/priority-list")
async def priority_list(limit: int = 50, components=Depends(get_components)) -> dict:
    jobs = await components.repo.priority_queue(limit=limit)
    return {
        "items": [
            {
                "job_id": j.id,
                "status": j.status,
                "priority": j.priority,
                "risk_score": j.risk_score,
                "category": j.category,
                "method_confidences": method_confidences(j.findings),
            }
            for j in jobs
        ]
    }
