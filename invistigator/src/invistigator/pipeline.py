import logging
from typing import Callable

from invistigator import osint
from invistigator.config import Settings
from invistigator.scraper import BanSignal
from invistigator.storage import append_jsonl, append_row, download_photo
from invistigator.trigger import post_channels

logger = logging.getLogger(__name__)


class Pipeline:
    def __init__(self, settings: Settings, scraper_factory: Callable):
        self.settings = settings
        self.scraper_factory = scraper_factory

    def process_username(self, scraper, username: str, sink: list | None = None):
        profile = scraper.fetch_profile(username)  # BanSignal пробрасываем наверх

        if profile.status == "ok" and profile.profile_pic:
            profile.profile_pic = download_photo(
                profile.profile_pic,
                profile.username,
                self.settings.media_dir,
                proxy=self.settings.http_proxy,
            )

        if self.settings.osint_enabled:
            profile.osint = osint.enrich(profile, self.settings)

        if profile.telegram_links:
            ok = post_channels(profile.telegram_links, self.settings.crawler_url)
            profile.tg_triggered = "yes" if ok else "error"

        append_row(profile, self.settings.csv_path)
        append_jsonl(profile, self.settings.jsonl_path)
        if sink is not None:
            sink.append(profile)
        logger.info(
            "%s → status=%s tg=%s", profile.username, profile.status, profile.tg_triggered
        )

    def process_batch(self, usernames: list[str], sink: list | None = None) -> None:
        # Скрейпер создаётся свежим на батч (важно для Playwright — один поток).
        scraper = self.scraper_factory()
        try:
            for username in usernames:
                try:
                    self.process_username(scraper, username, sink=sink)
                except BanSignal as exc:
                    logger.error("Останавливаю батч — признак бана: %s", exc)
                    break
                except Exception as exc:
                    logger.exception("Ошибка на %s: %s", username, exc)
        finally:
            close = getattr(scraper, "close", None)
            if callable(close):
                close()
