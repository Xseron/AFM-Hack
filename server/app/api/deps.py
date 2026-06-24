from __future__ import annotations

from fastapi import Request


def get_components(request: Request):
    return request.app.state.components
