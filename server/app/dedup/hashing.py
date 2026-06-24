from __future__ import annotations

import hashlib
from typing import AsyncIterator


def new_hasher():
    return hashlib.sha256()


async def tee_sha256(chunks: AsyncIterator[bytes], hasher) -> AsyncIterator[bytes]:
    """Yield each chunk unchanged while feeding it to `hasher` (single-pass)."""
    async for chunk in chunks:
        hasher.update(chunk)
        yield chunk
