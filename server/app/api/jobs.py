from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.api.deps import get_components
from app.api.serializers import method_confidences, scanner_confidences, source_info

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
        "method_confidences": method_confidences(job.findings),
        "scanner_confidences": scanner_confidences(job.findings),
        "source": source_info(job),
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


@router.get("/jobs/{job_id}/video")
async def get_job_video(job_id: str, components=Depends(get_components)):
    job = await components.repo.get_job(job_id)
    if job is None or not job.buffer_path or not os.path.isfile(job.buffer_path):
        raise HTTPException(status_code=404, detail="video not available")
    return FileResponse(job.buffer_path)
