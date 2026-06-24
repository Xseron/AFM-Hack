from app.pipelines.aggregator import aggregate
from app.pipelines.base import Finding


def test_empty_is_clean():
    score, category, exp = aggregate([])
    assert score == 0.0
    assert category == "clean"
    assert exp.scope == "aggregate"


def test_gambling_category_and_score():
    findings = [
        Finding(modality="visual", signal_type="casino_marker", confidence=0.45, evidence={}),
        Finding(modality="text", signal_type="text_signal:казино", confidence=0.5, evidence={}),
    ]
    score, category, exp = aggregate(findings)
    assert category == "gambling"
    assert 0.0 < score <= 1.0
    assert len(exp.attributions) == 2


def test_pyramid_category():
    findings = [Finding(modality="text", signal_type="text_signal:реферал", confidence=0.35, evidence={})]
    _, category, _ = aggregate(findings)
    assert category == "pyramid"


def test_score_clamped():
    findings = [Finding(modality="text", signal_type=f"s{i}", confidence=1.0, evidence={}) for i in range(20)]
    score, _, _ = aggregate(findings)
    assert score == 1.0
