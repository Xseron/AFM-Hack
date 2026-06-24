import asyncio
import logging

from aimw.crawler import ChannelAccessError, _normalize
from aimw.domain import ChannelReport
from aimw.prefilter import prefilter_text
from aimw.scoring import aggregate

log = logging.getLogger("aimw.pipeline")


class Pipeline:
    def __init__(self, crawler, analyzer, posts_per_channel: int):
        self._crawler = crawler
        self._analyzer = analyzer
        self._limit = posts_per_channel

    async def analyze_channel(self, username: str) -> ChannelReport:
        username = _normalize(username)
        log.info("Анализ канала '%s' (до %d постов)...", username, self._limit)
        try:
            title, posts = await self._crawler.fetch_channel(username, self._limit)
        except ChannelAccessError as exc:
            log.warning("Канал '%s' недоступен: %s", username, exc.reason)
            return ChannelReport(
                username=username, title=username, status="error", risk_score=0,
                categories=[], explanation="Канал недоступен.",
                post_assessments=[], error_reason=exc.reason,
            )

        to_analyze = [
            post for post in posts
            if prefilter_text(post.text)["is_suspicious"] or post.media_paths
        ]
        log.info(
            "Канал '%s' (%s): скачано %d постов, подозрительных к анализу — %d",
            username, title, len(posts), len(to_analyze),
        )

        assessments = list(await asyncio.gather(*(
            asyncio.to_thread(self._analyzer.analyze_post, post)
            for post in to_analyze
        )))

        agg = aggregate(assessments)
        log.info(
            "Канал '%s': риск-оценка %d, категории: %s",
            username, agg["risk_score"], agg["categories"] or "—",
        )
        return ChannelReport(
            username=username, title=title, status="ok",
            risk_score=agg["risk_score"], categories=agg["categories"],
            explanation=agg["explanation"], post_assessments=assessments,
        )
