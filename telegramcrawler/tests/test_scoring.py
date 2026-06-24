from aimw.domain import PostAssessment
from aimw.scoring import aggregate


def _pa(cats, conf):
    return PostAssessment(
        tg_message_id=1, categories=cats, confidence=conf,
        evidence_quotes=["q"], explanation="e", model_used="m",
    )


def test_empty_is_zero():
    r = aggregate([])
    assert r["risk_score"] == 0
    assert r["categories"] == []
    assert "не обнаружено" in r["explanation"]


def test_high_confidence_gambling_high_score():
    r = aggregate([_pa(["illegal_gambling"], 0.95)])
    assert r["risk_score"] >= 80
    assert "illegal_gambling" in r["categories"]


def test_low_weight_category_scores_lower_than_gambling():
    high = aggregate([_pa(["illegal_gambling"], 0.9)])["risk_score"]
    low = aggregate([_pa(["hidden_engagement"], 0.9)])["risk_score"]
    assert low < high


def test_more_suspicious_posts_increase_score():
    one = aggregate([_pa(["referral_scheme"], 0.6)])["risk_score"]
    many = aggregate([_pa(["referral_scheme"], 0.6) for _ in range(5)])["risk_score"]
    assert many > one


def test_score_capped_at_100():
    r = aggregate([_pa(["illegal_gambling"], 1.0) for _ in range(50)])
    assert r["risk_score"] == 100
