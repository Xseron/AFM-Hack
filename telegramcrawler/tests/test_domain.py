from datetime import datetime

from aimw.domain import RISK_CATEGORIES, Post, PostAssessment, ChannelReport


def test_risk_categories_exact():
    assert RISK_CATEGORIES == [
        "illegal_gambling",
        "financial_pyramid",
        "guaranteed_income",
        "aggressive_investment",
        "referral_scheme",
        "hidden_engagement",
    ]


def test_dataclasses_construct():
    post = Post(tg_message_id=1, date=datetime(2026, 1, 1), text="hi")
    assert post.media_paths == []
    pa = PostAssessment(
        tg_message_id=1,
        categories=["illegal_gambling"],
        confidence=0.9,
        evidence_quotes=["играй в казино"],
        explanation="ad",
        model_used="m",
    )
    report = ChannelReport(
        username="c", title="C", status="ok", risk_score=80,
        categories=["illegal_gambling"], explanation="x",
        post_assessments=[pa],
    )
    assert report.error_reason is None
    assert report.post_assessments[0].confidence == 0.9
