from __future__ import annotations

import logging

from app.pipelines.aggregator import aggregate
from app.pipelines.base import Finding, JobContext, Unit
from app.pipelines.explain import Explanation
from app.pipelines.registry import PipelineRegistry

log = logging.getLogger(__name__)

MODALITY_UNIT_KIND: dict[str, str] = {
    "text": "text",
    "ocr": "frame",
    "audio": "audio",
    "visual": "frame",
}


async def run_triage(
    ctx: JobContext, registry: PipelineRegistry
) -> tuple[float, list[Finding]]:
    text_unit = Unit(kind="text", index=0, payload={"text": ctx.description})
    findings: list[Finding] = []
    for pipeline in registry.triage_pipelines():
        try:
            produced = await pipeline.process(ctx, text_unit)
        except Exception as exc:  # one pipeline must not kill triage
            log.warning("triage pipeline %s failed: %s", getattr(pipeline, "name", "?"), exc)
            continue
        for f in produced:
            f.evidence.setdefault("_pipeline", pipeline.name)
        findings.extend(produced)
    priority = min(1.0, sum(f.confidence for f in findings))
    return priority, findings


async def run_analysis(
    ctx: JobContext,
    units: list[Unit],
    registry: PipelineRegistry,
    prior_findings: list[Finding] | None = None,
) -> tuple[list[Finding], list[Explanation], float, str]:
    all_findings: list[Finding] = []
    explanations: list[Explanation] = []
    video_unit = Unit(kind="video", index=0, payload={"path": ctx.buffer_path or ""})
    for pipeline in registry.analysis_pipelines():
        pipeline_findings: list[Finding] = []
        exp = None
        try:
            if getattr(pipeline, "whole_video", False):
                # Real model-backed pipelines analyze the whole video file once.
                pipeline_findings.extend(await pipeline.process(ctx, video_unit))
            else:
                wanted = MODALITY_UNIT_KIND.get(pipeline.modality)
                for unit in units:
                    if wanted is None or unit.kind == wanted:
                        pipeline_findings.extend(await pipeline.process(ctx, unit))
            exp = await pipeline.explain(ctx, pipeline_findings)
        except Exception as exc:  # one model must not fail the whole job
            log.warning("analysis pipeline %s failed: %s", getattr(pipeline, "name", "?"), exc)
            continue
        for f in pipeline_findings:
            f.evidence.setdefault("_pipeline", pipeline.name)
        all_findings.extend(pipeline_findings)
        if exp is not None:
            explanations.append(exp)

    score, category, agg_exp = aggregate(all_findings + list(prior_findings or []))
    explanations.append(agg_exp)
    return all_findings, explanations, score, category
