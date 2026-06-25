from app.pipelines.aggregator import aggregate
from app.pipelines.base import Finding


def test_empty_is_clean():
    score, category, exp = aggregate([])
    assert score == 0.0
    assert category == "clean"
    assert exp.scope == "aggregate"


def test_below_threshold_is_clean():
    # Default threshold is 0.5; nothing reaches it -> not scam.
    findings = [Finding(modality="text", signal_type="weak", confidence=0.3, evidence={})]
    score, category, _ = aggregate(findings)
    assert category == "clean"
    assert score == 0.3  # risk score is the max checker confidence


def test_gambling_when_checker_crosses_threshold():
    findings = [
        Finding(modality="visual", signal_type="casino_marker", confidence=0.45, evidence={}),
        Finding(modality="text", signal_type="text_signal:казино", confidence=0.5, evidence={}),
    ]
    score, category, exp = aggregate(findings)
    assert category == "gambling"
    assert score == 0.5
    assert len(exp.attributions) == 2


def test_pyramid_category_when_scam():
    findings = [Finding(modality="text", signal_type="text_signal:реферал", confidence=0.6, evidence={})]
    _, category, _ = aggregate(findings)
    assert category == "pyramid"


def test_score_is_max_and_clamped():
    findings = [Finding(modality="text", signal_type=f"s{i}", confidence=1.0, evidence={}) for i in range(20)]
    score, category, _ = aggregate(findings)
    assert score == 1.0
    assert category == "fraud"
