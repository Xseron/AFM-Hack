from app.pipelines.aggregator import (
    CLEAN,
    SCAM,
    SEMI_SCAM,
    aggregate,
    verdict_for,
)
from app.pipelines.base import Finding


def _f(confidence, pipeline=None):
    evidence = {"_pipeline": pipeline} if pipeline else {}
    return Finding(modality="text", signal_type="s", confidence=confidence, evidence=evidence)


def test_scam_when_threshold_reached():
    # Default threshold 0.5.
    assert verdict_for([_f(0.5)]) == SCAM


def test_semi_scam_between_two_thirds_and_full():
    # 0.5 / 1.5 == 0.333 <= 0.4 < 0.5 -> yellow.
    assert verdict_for([_f(0.4)]) == SEMI_SCAM


def test_clean_below_semi_threshold():
    assert verdict_for([_f(0.3)]) == CLEAN


def test_ignored_pipelines_never_decide_verdict():
    # Even a maxed-out deepfake / contact_spam finding stays clean on its own.
    assert verdict_for([_f(1.0, "deepfake_gend")]) == CLEAN
    assert verdict_for([_f(1.0, "contact_spam")]) == CLEAN


def test_ignored_pipeline_does_not_block_real_signal():
    findings = [_f(1.0, "contact_spam"), _f(0.5, "ocr_scam")]
    assert verdict_for(findings) == SCAM


def test_aggregate_marks_clean_when_only_ignored_pipelines_fire():
    score, category, exp = aggregate([_f(0.9, "deepfake_gend")])
    assert category == "clean"
    assert "verdict=clean" in exp.summary
    # risk score still reflects the raw signal for context.
    assert score == 0.9
