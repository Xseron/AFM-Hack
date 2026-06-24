from __future__ import annotations

from app.api.serializers import method_confidences
from app.db.repository import JobRepository
from app.pipelines.base import JobContext
from app.pipelines.extract import Extractor
from app.pipelines.orchestrator import run_analysis, run_triage
from app.pipelines.registry import PipelineRegistry
from app.queue.base import ANALYSIS, JobQueue, QueueMessage
from app.worker.base import Handler


def _ctx(job) -> JobContext:
    return JobContext(
        job_id=job.id,
        description=job.description,
        source_meta=job.source_meta or {},
        buffer_path=job.buffer_path,
    )


def make_triage_handler(repo: JobRepository, registry: PipelineRegistry, queue: JobQueue) -> Handler:
    async def handler(msg: QueueMessage) -> None:
        job = await repo.get_job(msg.job_id)
        if job is None:
            return
        priority = 0.0
        triage_error = None
        try:
            priority, findings = await run_triage(_ctx(job), registry)
            if findings:
                await repo.add_findings(job.id, findings)
        except Exception as exc:  # easy classifier is best-effort, never a gate
            triage_error = f"triage: {exc}"
        await repo.set_priority(job.id, priority)
        await repo.set_status(job.id, "triaged", error=triage_error)
        # Always enqueue for analysis — even if the easy classifier didn't pass or failed.
        await queue.enqueue(ANALYSIS, job.id, priority=priority)

    return handler


def _maybe_auto_scan(job, controller, auto_scan) -> None:
    """If enabled and the reel looks like a scam, scan its whole channel once."""
    if controller is None or auto_scan is None or not auto_scan.enabled:
        return
    confidences = method_confidences(job.findings)
    triggered = [m for m, v in confidences.items() if v >= auto_scan.thresholds.get(m, 1.0)]
    if not triggered:
        return
    meta = job.source_meta or {}
    author = (meta.get("author") or "").strip()
    channel = meta.get("channel_url") or (f"https://www.instagram.com/{author}/" if author else "")
    if not channel:
        return
    key = (author or channel).lower()
    if key in auto_scan.scanned:
        return
    try:
        controller.start(channel, max_reels=auto_scan.max_reels)
        auto_scan.scanned.add(key)
        print(f"[auto-scan] scam in {job.id} via {', '.join(triggered)}; scanning {channel}")
    except RuntimeError:
        pass  # parser busy; a later scam hit on this channel will retry


def make_analysis_handler(
    repo: JobRepository,
    registry: PipelineRegistry,
    extractor: Extractor,
    controller=None,
    auto_scan=None,
) -> Handler:
    async def handler(msg: QueueMessage) -> None:
        job = await repo.get_job(msg.job_id)
        if job is None:
            return
        await repo.set_status(job.id, "processing")
        try:
            ctx = _ctx(job)
            units = await extractor.extract(ctx)
            # Triage findings (saved earlier) also feed the risk aggregate.
            triage_prior = [f for f in job.findings if f.modality == "triage"]
            findings, explanations, score, category = await run_analysis(
                ctx, units, registry, prior_findings=triage_prior
            )
            await repo.add_findings(job.id, findings)
            await repo.add_explanations(job.id, explanations)
            await repo.set_risk(job.id, score, category)
            await repo.set_status(job.id, "done")
        except Exception as exc:
            await repo.set_status(job.id, "failed", error=str(exc))
            return
        fresh = await repo.get_job(job.id)
        if fresh is not None:
            _maybe_auto_scan(fresh, controller, auto_scan)

    return handler
