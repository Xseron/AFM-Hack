from __future__ import annotations

from pathlib import Path
from typing import AsyncIterator


class LocalStorage:
    def __init__(self, root: str) -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)

    def path_for(self, key: str) -> str:
        return str(self._root / key)

    async def save_stream(self, key: str, chunks: AsyncIterator[bytes]) -> str:
        target = self._root / key
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "wb") as fh:
            async for chunk in chunks:
                fh.write(chunk)
        return str(target)

    async def delete(self, key: str) -> None:
        (self._root / key).unlink(missing_ok=True)
