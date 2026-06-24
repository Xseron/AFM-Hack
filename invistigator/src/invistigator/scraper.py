import random
import time
from datetime import datetime, timezone

import instaloader
import requests

from invistigator.config import Settings
from invistigator.linkdetect import find_telegram_links
from invistigator.schemas import ProfileData

# Публичный web-app id Instagram — обязателен для web_profile_info.
APP_ID = "936619743392459"
PROFILE_URL = "https://i.instagram.com/api/v1/users/web_profile_info/"


class BanSignal(Exception):
    """Поднимается при признаках бана/лимита — пайплайн должен остановить батч."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def profile_from_user_json(user: dict, fallback_username: str) -> ProfileData:
    """Маппит объект `data.user` (web_profile_info) в ProfileData. Общий для обоих скрейперов."""
    if user is None:
        return ProfileData(username=fallback_username, status="not_found", scraped_at=_now())

    external = user.get("external_url")
    bio = user.get("biography")
    bio_link_urls = [l.get("url") for l in (user.get("bio_links") or []) if l.get("url")]
    tg = find_telegram_links(external, bio, *bio_link_urls)

    # Две формы ответа: web_profile_info (edge_followed_by/profile_pic_url_hd)
    # и graphql-профиль (follower_count/hd_profile_pic_url_info).
    followers = user.get("follower_count")
    if followers is None:
        followers = (user.get("edge_followed_by") or {}).get("count")
    pic = (
        user.get("profile_pic_url_hd")
        or (user.get("hd_profile_pic_url_info") or {}).get("url")
        or user.get("profile_pic_url")
        or ""
    )

    return ProfileData(
        username=user.get("username") or fallback_username,
        full_name=user.get("full_name"),
        biography=bio,
        external_url=external,
        profile_pic=pic,
        followers=followers,
        is_private=bool(user.get("is_private")),
        telegram_links=tg,
        status="private" if user.get("is_private") else "ok",
        scraped_at=_now(),
    )


class Scraper:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._last_fetch = 0.0

        self.loader = instaloader.Instaloader(
            quiet=True,
            download_pictures=False,
            download_videos=False,
            download_comments=False,
            save_metadata=False,
            request_timeout=30,
        )

        # Сессию грузим один раз; повторный логин — главный триггер бана.
        try:
            self.loader.load_session_from_file(
                settings.ig_username, settings.ig_session_file
            )
        except FileNotFoundError as exc:
            raise RuntimeError(
                f"Session-файл '{settings.ig_session_file}' не найден — "
                "сначала запусти `python scripts/login.py`"
            ) from exc

        # ВАЖНО: настраиваем сессию ПОСЛЕ load_session_from_file —
        # он создаёт новую requests.Session и затирает любые ранее заданные
        # заголовки/прокси.
        session = self.loader.context._session
        if settings.http_proxy:
            session.proxies.update({"http": settings.http_proxy, "https": settings.http_proxy})
        session.headers["X-IG-App-ID"] = APP_ID

    def _throttle(self) -> None:
        """Рандомная пауза между профилями (анти-бан)."""
        elapsed = time.monotonic() - self._last_fetch
        delay = random.uniform(self.settings.min_delay_sec, self.settings.max_delay_sec)
        if elapsed < delay:
            time.sleep(delay - elapsed)
        self._last_fetch = time.monotonic()

    def fetch_profile(self, username: str) -> ProfileData:
        username = username.strip().lstrip("@").rstrip("/").split("/")[-1]
        self._throttle()

        session = self.loader.context._session
        try:
            resp = session.get(
                PROFILE_URL,
                params={"username": username},
                headers={
                    "X-IG-App-ID": APP_ID,
                    "Referer": f"https://www.instagram.com/{username}/",
                },
                timeout=30,
            )
        except requests.RequestException:
            return ProfileData(username=username, status="error", scraped_at=_now())

        if resp.status_code == 404:
            return ProfileData(username=username, status="not_found", scraped_at=_now())
        if resp.status_code == 429:
            raise BanSignal(f"rate-limited (429) на {username}")
        if resp.status_code in (401, 403):
            raise BanSignal(f"бан/челлендж ({resp.status_code}) на {username}")
        if resp.status_code != 200:
            return ProfileData(username=username, status="error", scraped_at=_now())

        try:
            user = resp.json()["data"]["user"]
        except (ValueError, KeyError):
            return ProfileData(username=username, status="error", scraped_at=_now())

        return profile_from_user_json(user, username)
