from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api import investigation
from app.config import Settings


def _app(monkeypatch, handler):
    """Build an app whose proxy uses a mock httpx transport calling `handler`."""
    app = FastAPI()
    app.include_router(investigation.router)

    class _Comp:
        settings = Settings(_env_file=None)

    app.state.components = _Comp()

    real_async_client = httpx.AsyncClient

    def fake_client(*args, **kwargs):
        kwargs.pop("timeout", None)
        return real_async_client(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(investigation.httpx, "AsyncClient", fake_client)
    return app


@pytest.mark.asyncio
async def test_graph_passthrough(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/graph"
        return httpx.Response(200, json={"nodes": [{"id": "account:x"}], "edges": []})

    app = _app(monkeypatch, handler)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/osint/graph?min_shared=3")
    assert r.status_code == 200
    body = r.json()
    assert body["available"] is True
    assert body["nodes"] == [{"id": "account:x"}]


@pytest.mark.asyncio
async def test_graph_offline_returns_available_false(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    app = _app(monkeypatch, handler)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/osint/graph")
    assert r.status_code == 200
    body = r.json()
    assert body["available"] is False
    assert "reason" in body


@pytest.mark.asyncio
async def test_post_accounts_forwards_body(monkeypatch):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["json"] = request.read().decode()
        return httpx.Response(200, json={"job_id": "j1", "accepted": 2})

    app = _app(monkeypatch, handler)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/osint/accounts", json={"usernames": ["a", "b"]})
    assert r.json()["available"] is True
    assert r.json()["job_id"] == "j1"
    assert "usernames" in seen["json"]
