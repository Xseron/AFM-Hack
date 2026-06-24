from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Attribution:
    feature: str
    value: str | float
    weight: float


@dataclass
class Explanation:
    scope: str
    method: str
    attributions: list[Attribution]
    summary: str
    media: bytes | None = None
