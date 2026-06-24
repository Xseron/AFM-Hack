from app.pipelines.base import Finding, JobContext, Unit
from app.pipelines.explain import Attribution, Explanation


def test_unit_and_finding():
    u = Unit(kind="text", index=0, payload={"text": "hi"})
    assert u.payload["text"] == "hi"
    f = Finding(modality="text", signal_type="kw", confidence=0.5, evidence={"k": 1})
    assert f.ts_in_video is None


def test_job_context_defaults():
    ctx = JobContext(job_id="j1", description="d", source_meta={})
    assert ctx.buffer_path is None


def test_explanation_holds_attributions():
    exp = Explanation(
        scope="aggregate",
        method="shap",
        attributions=[Attribution(feature="casino", value=1.0, weight=0.5)],
        summary="x",
    )
    assert exp.attributions[0].weight == 0.5
    assert exp.media is None
