from __future__ import annotations

from dataclasses import dataclass, field
from typing import AsyncIterator, Protocol


@dataclass
class SourceItem:
    video_path: str
    description: str
    platform: str
    url: str | None = None
    meta: dict = field(default_factory=dict)


class Source(Protocol):
    def fetch(self) -> AsyncIterator[SourceItem]: ...
