from __future__ import annotations

from typing import Protocol

from app.pipelines.base import JobContext, Unit


class Extractor(Protocol):
    async def extract(self, ctx: JobContext) -> list[Unit]: ...


class StubExtractor:
    """Deterministic stand-in for ffmpeg/PyAV frame & audio extraction."""

    def __init__(self, n_frames: int = 3, n_audio: int = 2) -> None:
        self._n_frames = n_frames
        self._n_audio = n_audio

    async def extract(self, ctx: JobContext) -> list[Unit]:
        units: list[Unit] = [Unit(kind="text", index=0, payload={"text": ctx.description})]
        units += [Unit(kind="frame", index=i, payload={"ts": float(i)}) for i in range(self._n_frames)]
        units += [Unit(kind="audio", index=i, payload={"ts": float(i * 5)}) for i in range(self._n_audio)]
        return units
