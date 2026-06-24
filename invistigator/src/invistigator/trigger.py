import logging

import httpx

logger = logging.getLogger(__name__)


def post_channels(channels: list[str], crawler_url: str) -> bool:
    """Шлёт TG-каналы в telegramcrawler. Недоступность crawler не роняет пайплайн."""
    if not channels:
        return False
    try:
        resp = httpx.post(
            f"{crawler_url.rstrip('/')}/channels",
            json={"channels": channels},
            timeout=120,
        )
        resp.raise_for_status()
        return True
    except Exception as exc:
        logger.warning("telegramcrawler недоступен (%s): %s", channels, exc)
        return False
