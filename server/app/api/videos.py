from __future__ import annotations

import json
import uuid
from typing import AsyncIterator

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.api.deps import get_components
from app.dedup.hashing import new_hasher, tee_sha256
from app.pipelines.base import JobContext
from app.queue.base import INTAKE

router = APIRouter()


async def _chunks(
    upload: UploadFile, chunk_size: int = 1 << 20
) -> AsyncIterator[bytes]:
    while True:
        chunk = await upload.read(chunk_size)
        if not chunk:
            break
        yield chunk


@router.post("/videos", status_code=202)
async def ingest_video(
    video: UploadFile = File(...),
    description: str = Form(...),
    source_platform: str | None = Form(None),
    source_url: str | None = Form(None),
    source_meta: str | None = Form(None),
    components=Depends(get_components),
) -> dict:
    if not description.strip():
        raise HTTPException(status_code=422, detail="description must not be empty")
    if video.content_type and not video.content_type.startswith("video/"):
        raise HTTPException(status_code=415, detail="expected a video/* upload")

    limit = components.settings.max_upload_bytes
    if video.size is not None and video.size > limit:
        raise HTTPException(status_code=413, detail=f"video exceeds max {limit} bytes")

    meta: dict = {}
    if source_meta:
        try:
            meta = json.loads(source_meta)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=422, detail="source_meta must be valid JSON"
            )

    # Stream to a temp buffer key while computing SHA-256 in the same pass (no full file in RAM).
    filename = video.filename or "video.bin"
    temp_key = f"incoming/{uuid.uuid4().hex}/{filename}"
    hasher = new_hasher()
    path = await components.storage.save_stream(
        temp_key, tee_sha256(_chunks(video), hasher)
    )
    content_hash = hasher.hexdigest()

    # Exact dedup: identical content already ingested -> short-circuit (no new job, no enqueue).
    existing = await components.repo.get_job_by_hash(content_hash)
    if existing is not None:
        await components.storage.delete(temp_key)
        return {"job_id": existing.id, "duplicate": True, "near_duplicates": []}

    job_id = await components.repo.create_job(
        description,
        source_platform,
        source_url,
        meta,
        buffer_path=path,
        content_hash=content_hash,
    )
    ctx = JobContext(
        job_id=job_id, description=description, source_meta=meta, buffer_path=path
    )
    near_duplicates = await components.neardup.find_similar(
        ctx
    )  # [] from NullNearDupIndex seam
    await components.neardup.index(ctx)
    await components.queue.enqueue(INTAKE, job_id)
    return {"job_id": job_id, "duplicate": False, "near_duplicates": near_duplicates}
