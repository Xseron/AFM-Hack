import asyncio
from datetime import datetime

from aimw.crawler import ChannelAccessError
from aimw.domain import Post, PostAssessment
from aimw.pipeline import Pipeline


class FakeCrawler:
    def __init__(self, posts, error=None):
        self._posts = posts
        self._error = error

    async def fetch_channel(self, username, limit):
        if self._error:
            raise self._error
        return "Title", self._posts


class FakeAnalyzer:
    def __init__(self):
        self.analyzed_ids = []

    def analyze_post(self, post):
        self.analyzed_ids.append(post.tg_message_id)
        return PostAssessment(
            tg_message_id=post.tg_message_id, categories=["illegal_gambling"],
            confidence=0.9, evidence_quotes=["казино"], explanation="ad",
            model_used="m",
        )


def test_only_suspicious_posts_analyzed():
    posts = [
        Post(1, datetime(2026, 1, 1), "лучшее казино, делай ставки"),
        Post(2, datetime(2026, 1, 1), "сегодня гуляли в парке"),
    ]
    analyzer = FakeAnalyzer()
    pipe = Pipeline(FakeCrawler(posts), analyzer, posts_per_channel=50)
    report = asyncio.run(pipe.analyze_channel("chan"))
    assert analyzer.analyzed_ids == [1]  # only the gambling post
    assert report.status == "ok"
    assert report.risk_score >= 80
    assert "illegal_gambling" in report.categories


def test_access_error_becomes_error_report():
    pipe = Pipeline(
        FakeCrawler([], error=ChannelAccessError("chan", "private")),
        FakeAnalyzer(), posts_per_channel=50,
    )
    report = asyncio.run(pipe.analyze_channel("chan"))
    assert report.status == "error"
    assert report.error_reason == "private"
    assert report.risk_score == 0


def test_clean_channel_zero_score():
    posts = [Post(1, datetime(2026, 1, 1), "хорошая погода сегодня")]
    pipe = Pipeline(FakeCrawler(posts), FakeAnalyzer(), posts_per_channel=50)
    report = asyncio.run(pipe.analyze_channel("chan"))
    assert report.risk_score == 0
    assert report.status == "ok"
