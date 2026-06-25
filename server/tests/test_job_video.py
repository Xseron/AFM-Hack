from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api import jobs


class _Repo:
    def __init__(self, job):
        self._job = job

    async def get_job(self, job_id):
        return self._job


class _Job:
    def __init__(self, buffer_path):
        self.buffer_path = buffer_path


def _app(job):
    app = FastAPI()
    app.include_router(jobs.router)

    class _Comp:
        repo = _Repo(job)

    app.state.components = _Comp()
    return app


@pytest.mark.asyncio
async def test_video_served_when_present(tmp_path):
    f = tmp_path / "v.mp4"
    f.write_bytes(b"\x00\x01\x02fakevideo")
    app = _app(_Job(str(f)))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/jobs/abc/video")
    assert r.status_code == 200
    assert r.content == b"\x00\x01\x02fakevideo"


@pytest.mark.asyncio
async def test_video_404_when_missing(tmp_path):
    app = _app(_Job(str(tmp_path / "nope.mp4")))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/jobs/abc/video")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_video_404_when_no_job():
    app = _app(None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/jobs/abc/video")
    assert r.status_code == 404
