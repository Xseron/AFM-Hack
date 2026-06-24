from app.pipelines.base import JobContext, Unit
from app.pipelines.registry import PipelineRegistry
from app.pipelines.stubs import (
    AudioPipeline,
    TextPipeline,
    TriageClassifier,
    VisualPipeline,
    register_default_pipelines,
)


def _ctx(desc):
    return JobContext(job_id="j", description=desc, source_meta={})


async def test_triage_matches_keywords_and_explains():
    p = TriageClassifier()
    ctx = _ctx("Лучшее КАЗИНО и гарантированный доход")
    findings = await p.process(ctx, Unit(kind="text", index=0, payload={"text": ctx.description}))
    kinds = {f.signal_type for f in findings}
    assert any("казино" in k for k in kinds)
    exp = await p.explain(ctx, findings)
    assert exp.scope == "triage"
    assert exp.attributions


async def test_triage_clean_text_no_findings():
    p = TriageClassifier()
    ctx = _ctx("милые котики на природе")
    findings = await p.process(ctx, Unit(kind="text", index=0, payload={"text": ctx.description}))
    assert findings == []


async def test_visual_emits_marker_for_casino():
    p = VisualPipeline()
    ctx = _ctx("реклама casino")
    findings = await p.process(ctx, Unit(kind="frame", index=0, payload={"ts": 0.0}))
    assert findings and findings[0].signal_type == "casino_marker"
    assert findings[0].modality == "visual"


async def test_audio_promise_detected():
    p = AudioPipeline()
    ctx = _ctx("обещаю доход каждый день")
    findings = await p.process(ctx, Unit(kind="audio", index=0, payload={"ts": 0.0}))
    assert findings and findings[0].signal_type == "speech_promise"


async def test_register_default_pipelines():
    reg = register_default_pipelines(PipelineRegistry())
    assert {p.modality for p in reg.all()} >= {"triage", "text", "ocr", "audio", "visual"}
    assert len(reg.triage_pipelines()) == 1
