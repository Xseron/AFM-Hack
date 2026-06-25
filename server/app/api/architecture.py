"""Read/edit the live analysis pipeline architecture from the UI."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import get_components

router = APIRouter(prefix="/architecture")


class NodeUpdate(BaseModel):
    enabled: bool | None = None
    threshold: float | None = None


class AggregateUpdate(BaseModel):
    default_threshold: float


class EdgeUpdate(BaseModel):
    from_id: str
    to_id: str


@router.get("")
async def get_architecture(components=Depends(get_components)) -> dict:
    return components.architecture.graph(components.auto_scan)


@router.post("/node/{node_id}")
async def update_node(node_id: str, body: NodeUpdate, components=Depends(get_components)) -> dict:
    try:
        node = components.architecture.set_node(node_id, enabled=body.enabled, threshold=body.threshold)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"unknown node: {node_id}") from exc
    return node


@router.delete("/node/{node_id}")
async def delete_node(node_id: str, components=Depends(get_components)) -> dict:
    try:
        components.architecture.remove_node(node_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return components.architecture.graph(components.auto_scan)


@router.post("/aggregate")
async def update_aggregate(body: AggregateUpdate, components=Depends(get_components)) -> dict:
    threshold = components.architecture.set_default_threshold(body.default_threshold)
    return {"default_threshold": threshold}


@router.post("/edge")
async def connect_edge(body: EdgeUpdate, components=Depends(get_components)) -> dict:
    if body.to_id == "investigate":
        components.auto_scan.enabled = True
        return components.architecture.graph(components.auto_scan)
    try:
        components.architecture.connect_edge(body.from_id, body.to_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"unknown node: {body.to_id}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return components.architecture.graph(components.auto_scan)


@router.post("/edge/remove")
async def remove_edge(body: EdgeUpdate, components=Depends(get_components)) -> dict:
    if body.to_id == "investigate":
        components.auto_scan.enabled = False
        return components.architecture.graph(components.auto_scan)
    try:
        components.architecture.disconnect_edge(body.from_id, body.to_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"unknown node: {body.to_id}") from exc
    return components.architecture.graph(components.auto_scan)


@router.post("/reload")
async def reload_plugins(components=Depends(get_components)) -> dict:
    components.architecture.reload_plugins()
    return components.architecture.graph(components.auto_scan)
