from __future__ import annotations

from typing import Protocol

from app.pipelines.base import JobContext


class NearDupIndex(Protocol):
    async def find_similar(self, ctx: JobContext) -> list[str]: ...

    async def index(self, ctx: JobContext) -> None: ...


class NullNearDupIndex:
    """Seam for perceptual near-duplicate detection.

    A real implementation computes a perceptual fingerprint (pHash over frames,
    audio fingerprint, or an embedding) from ``ctx.buffer_path`` and queries a
    similarity/vector index. The skeleton ships this no-op so the call sites and
    API contract exist now.
    """

    async def find_similar(self, ctx: JobContext) -> list[str]:
        return []

    async def index(self, ctx: JobContext) -> None:
        return None
