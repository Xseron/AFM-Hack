from __future__ import annotations

import httpx
from fastapi import APIRouter, Body, Depends

from app.api.deps import get_components

router = APIRouter()


async def _proxy(
    method: str,
    url: str,
    *,
    timeout: float,
    json: dict | None = None,
    params: dict | None = None,
) -> dict:
    """Forward a request to an external OSINT service.

    Returns the upstream JSON merged with ``available: True``. On any connection
    or timeout error (service down), returns ``{"available": False, "reason": ...}``
    so the browser shows an offline banner instead of an error page.
    """
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.request(method, url, json=json, params=params)
            resp.raise_for_status()
            payload = resp.json()
    except (httpx.HTTPError, ValueError) as exc:  # ValueError: bad JSON
        return {"available": False, "reason": str(exc)}
    if isinstance(payload, list):
        return {"available": True, "items": payload}
    return {"available": True, **payload}


@router.get("/osint/graph")
async def osint_graph(min_shared: int = 2, components=Depends(get_components)) -> dict:
    s = components.settings
    return await _proxy(
        "GET",
        f"{s.investigator_url.rstrip('/')}/graph",
        timeout=s.httpx_timeout_seconds,
        params={"min_shared": min_shared},
    )


@router.get("/osint/accounts/{job_id}")
async def osint_account_job(job_id: str, components=Depends(get_components)) -> dict:
    s = components.settings
    return await _proxy(
        "GET",
        f"{s.investigator_url.rstrip('/')}/accounts/{job_id}",
        timeout=s.httpx_timeout_seconds,
    )


@router.post("/osint/accounts")
async def osint_accounts(
    body: dict = Body(...), components=Depends(get_components)
) -> dict:
    s = components.settings
    return await _proxy(
        "POST",
        f"{s.investigator_url.rstrip('/')}/accounts",
        timeout=s.httpx_timeout_seconds,
        json=body,
    )


@router.get("/telegram/channels")
async def telegram_channels(sort: str = "risk", components=Depends(get_components)) -> dict:
    s = components.settings
    return await _proxy(
        "GET",
        f"{s.telegram_url.rstrip('/')}/channels",
        timeout=s.httpx_timeout_seconds,
        params={"sort": sort},
    )


@router.get("/telegram/channels/{username}")
async def telegram_channel(username: str, components=Depends(get_components)) -> dict:
    s = components.settings
    return await _proxy(
        "GET",
        f"{s.telegram_url.rstrip('/')}/channels/{username}",
        timeout=s.httpx_timeout_seconds,
    )
