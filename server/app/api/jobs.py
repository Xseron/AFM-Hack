from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_components

router = APIRouter()


@router.get("/jobs/{job_id}")
async def get_job(job_id: str, components=Depends(get_components)) -> dict:
    job = await components.repo.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return {
        "job_id": job.id,
        "status": job.status,
        "priority": job.priority,
        "risk_score": job.risk_score,
        "category": job.category,
        "description": job.description,
        "error": job.error,
        "findings": [
            {
                "modality": f.modality,
                "signal_type": f.signal_type,
                "confidence": f.confidence,
                "evidence": f.evidence,
                "ts_in_video": f.ts_in_video,
            }
            for f in job.findings
        ],
    }


@router.get("/jobs/{job_id}/explanations")
async def get_explanations(job_id: str, components=Depends(get_components)) -> dict:
    job = await components.repo.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return {
        "job_id": job.id,
        "explanations": [
            {"scope": e.scope, "method": e.method, "summary": e.summary, "payload": e.payload}
            for e in job.explanations
        ],
    }
