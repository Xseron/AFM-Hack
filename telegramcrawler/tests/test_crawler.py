import asyncio
from datetime import datetime

import pytest

from aimw.crawler import Crawler, ChannelAccessError


class FakeMessage:
    def __init__(self, mid, text, photo=None):
        self.id = mid
        self.message = text
        self.date = datetime(2026, 1, 1)
        self.photo = photo


class FakeClient:
    def __init__(self, title, messages, raise_on_entity=False):
        self._title = title
        self._messages = messages
        self._raise = raise_on_entity

    async def get_entity(self, username):
        if self._raise:
            raise ValueError("No user has that username")
        return type("E", (), {"title": self._title})()

    async def iter_messages(self, entity, limit=50):
        for m in self._messages[:limit]:
            yield m

    async def download_media(self, message, file=None):
        with open(file, "wb") as f:
            f.write(b"img")
        return file


def test_fetch_channel_returns_posts(tmp_path):
    client = FakeClient("My Channel", [FakeMessage(1, "казино"), FakeMessage(2, "hi")])
    crawler = Crawler(client, media_dir=str(tmp_path))
    title, posts = asyncio.run(crawler.fetch_channel("chan", limit=50))
    assert title == "My Channel"
    assert [p.tg_message_id for p in posts] == [1, 2]
    assert posts[0].text == "казино"


def test_fetch_channel_downloads_photo(tmp_path):
    client = FakeClient("C", [FakeMessage(1, "see image", photo=object())])
    crawler = Crawler(client, media_dir=str(tmp_path))
    _, posts = asyncio.run(crawler.fetch_channel("chan", limit=50))
    assert len(posts[0].media_paths) == 1


def test_inaccessible_channel_raises(tmp_path):
    client = FakeClient("C", [], raise_on_entity=True)
    crawler = Crawler(client, media_dir=str(tmp_path))
    with pytest.raises(ChannelAccessError) as exc:
        asyncio.run(crawler.fetch_channel("nope", limit=50))
    assert exc.value.username == "nope"
