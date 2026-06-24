
from __future__ import annotations

from typing import AsyncIterator, Protocol


class BlobStorage(Protocol):
    async def save_stream(self, key: str, chunks: AsyncIterator[bytes]) -> str: ...

    def path_for(self, key: str) -> str: ...

    async def delete(self, key: str) -> None: ...
