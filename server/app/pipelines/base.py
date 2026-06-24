from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from app.pipelines.explain import Explanation


@dataclass
class Unit:
    kind: str          # "text" | "frame" | "audio"
    index: int
    payload: dict = field(default_factory=dict)


@dataclass
class Finding:
    modality: str      # "triage" | "text" | "ocr" | "audio" | "visual"
    signal_type: str
    confidence: float
    evidence: dict = field(default_factory=dict)
    ts_in_video: float | None = None


@dataclass
class JobContext:
    job_id: str
    description: str
    source_meta: dict = field(default_factory=dict)
    buffer_path: str | None = None


@runtime_checkable
class Pipeline(Protocol):
    name: str
    modality: str

    async def process(self, ctx: JobContext, unit: Unit) -> list[Finding]: ...

    async def explain(self, ctx: JobContext, findings: list[Finding]) -> Explanation | None: ...
