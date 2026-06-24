from __future__ import annotations

from typing import AsyncIterator

from app.sources.base import SourceItem


class StubSource:
    """Placeholder collector. Real TikTok/Instagram scrapers replace this later."""

    def __init__(self, items: list[SourceItem] | None = None) -> None:
        self._items = items if items is not None else [
            SourceItem(
                video_path="sample/clip.mp4",
                description="Лучшее онлайн казино, гарантированный доход 200% по реферальной ссылке",
                platform="tiktok",
                url="https://example.com/clip",
                meta={"author": "@stub"},
            )
        ]

    async def fetch(self) -> AsyncIterator[SourceItem]:
        for item in self._items:
            yield item
