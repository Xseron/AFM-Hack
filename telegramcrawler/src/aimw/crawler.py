import logging
import os

from telethon import TelegramClient

from aimw.domain import Post

log = logging.getLogger("aimw.crawler")


class ChannelAccessError(Exception):
    def __init__(self, username: str, reason: str):
        super().__init__(f"{username}: {reason}")
        self.username = username
        self.reason = reason


def build_telethon_client(settings) -> TelegramClient:
    return TelegramClient(
        settings.telegram_session,
        settings.telegram_api_id,
        settings.telegram_api_hash,
    )


def _normalize(username: str) -> str:
    u = username.strip()
    for prefix in ("https://t.me/", "http://t.me/", "t.me/", "@"):
        if u.startswith(prefix):
            u = u[len(prefix):]
    return u.strip("/")


class Crawler:
    def __init__(self, client, media_dir: str = "media"):
        self._client = client
        self._media_dir = media_dir
        os.makedirs(media_dir, exist_ok=True)

    async def fetch_channel(self, username: str, limit: int) -> tuple[str, list[Post]]:
        name = _normalize(username)
        try:
            entity = await self._client.get_entity(name)
        except Exception as exc:  # noqa: BLE001
            raise ChannelAccessError(username, str(exc)) from exc

        title = getattr(entity, "title", name)
        posts: list[Post] = []
        async for message in self._client.iter_messages(entity, limit=limit):
            text = getattr(message, "message", None) or ""
            media_paths: list[str] = []
            if getattr(message, "photo", None) is not None:
                path = os.path.join(self._media_dir, f"{name}_{message.id}.jpg")
                log.info("Скачиваю фото из поста %d канала '%s'...", message.id, name)
                saved = await self._client.download_media(message, file=path)
                if saved:
                    media_paths.append(saved)
            posts.append(Post(
                tg_message_id=message.id,
                date=message.date,
                text=text,
                media_paths=media_paths,
            ))
        return title, posts
