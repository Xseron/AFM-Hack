"""Real model-backed pipelines (replace the stubs when MW_MODELS_ENABLED=true).

Each pipeline wraps a detector loaded in `app.models.loader.Models`, runs on the
buffered video file (`ctx.buffer_path`) exactly once (`whole_video = True`), and
offloads the blocking model call to a worker thread. If the pipeline's model
failed to load (missing dependency/weights), `process` returns `[]` so the rest
of the analysis still runs.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from app.models.loader import Models
from app.pipelines.base import Finding, JobContext, Unit
from app.pipelines.explain import Attribution, Explanation
from app.pipelines.registry import PipelineRegistry


def _video_path(ctx: JobContext) -> Path | None:
    if not ctx.buffer_path:
        return None
    path = Path(ctx.buffer_path)
    return path if path.exists() else None


def _top_term(matched_terms: list) -> str:
    return matched_terms[0].term if matched_terms else "scam"


def _term_pairs(matched_terms: list, limit: int = 8) -> list[list]:
    return [[hit.term, hit.contribution] for hit in matched_terms[:limit]]


def _term_attrs(pairs: list[list]) -> list[Attribution]:
    return [Attribution(feature=term, value=contribution, weight=contribution) for term, contribution in pairs]


class WhisperKeywordTriage:
    """Easy classifier: video -> Whisper transcript -> Russian scam keyword score.

    Falls back to scoring the post caption (``ctx.description``) when Whisper is
    unavailable, so triage still yields a priority signal.
    """

    name = "triage_whisper_keyword"
    modality = "triage"
    whole_video = True

    def __init__(self, models: Models) -> None:
        self._m = models

    async def process(self, ctx: JobContext, unit: Unit) -> list[Finding]:
        if self._m.keyword_detector is None:
            return []
        result = await asyncio.to_thread(self._classify, ctx)
        if result is None:
            return []
        probability, matched = result
        return [
            Finding(
                modality="triage",
                signal_type=f"speech_scam:{_top_term(matched)}",
                confidence=float(probability),
                evidence={"source": "whisper" if self._m.whisper else "caption"},  # "top_terms": _term_pairs(matched),
            )
        ]

    def _classify(self, ctx: JobContext):
        import audio_detect as ad

        video_path = _video_path(ctx)
        transcript = None
        if self._m.whisper is not None and video_path is not None:
            try:
                transcript = self._m.whisper.transcribe(video_path, self._m.transcripts_dir, force=False)
            except Exception:
                transcript = None  # no speech / decode error -> fall back to caption text
        if transcript is None:
            text = (ctx.description or "").strip()
            if not text:
                return None
            transcript = ad.Transcript(video_path=Path("<caption>"), text_path=Path("<none>"), text=text)
        try:
            result = self._m.keyword_detector.classify(transcript)
        except ValueError:
            return None
        return result.scam_probability, result.matched_terms

    async def explain(self, ctx: JobContext, findings: list[Finding]) -> Explanation | None:
        if not findings:
            return None
        return Explanation(
            scope="triage",
            method="keyword",
            attributions=_term_attrs(findings[0].evidence.get("top_terms", [])),
            summary=f"speech scam probability {findings[0].confidence:.2f}",
        )


class CaptionTextPipeline:
    """Score the post caption/description text with the scam keyword detector."""

    name = "caption_text"
    modality = "text"
    whole_video = True

    def __init__(self, models: Models) -> None:
        self._m = models

    async def process(self, ctx: JobContext, unit: Unit) -> list[Finding]:
        if self._m.keyword_detector is None:
            return []
        text = (ctx.description or "").strip()
        if not text:
            return []
        result = await asyncio.to_thread(self._run, text)
        if result is None:
            return []
        return [
            Finding(
                modality="text",
                signal_type=f"caption_scam:{_top_term(result.matched_terms)}",
                confidence=float(result.scam_probability),
                evidence={},  # "top_terms": _term_pairs(result.matched_terms),
            )
        ]

    def _run(self, text: str):
        import audio_detect as ad

        transcript = ad.Transcript(video_path=Path("<caption>"), text_path=Path("<none>"), text=text)
        try:
            return self._m.keyword_detector.classify(transcript)
        except ValueError:
            return None

    async def explain(self, ctx: JobContext, findings: list[Finding]) -> Explanation | None:
        if not findings:
            return None
        return Explanation(
            scope="text",
            method="keyword",
            attributions=_term_attrs(findings[0].evidence.get("top_terms", [])),
            summary=f"caption scam probability {findings[0].confidence:.2f}",
        )


class AudioScamPipeline:
    """Audio speech scam detection: Whisper transcript (cached) -> keyword score."""

    name = "audio_scam"
    modality = "audio"
    whole_video = True

    def __init__(self, models: Models) -> None:
        self._m = models

    async def process(self, ctx: JobContext, unit: Unit) -> list[Finding]:
        if self._m.whisper is None or self._m.keyword_detector is None:
            return []
        video_path = _video_path(ctx)
        if video_path is None:
            return []
        result = await asyncio.to_thread(self._run, video_path)
        if result is None:
            return []
        return [
            Finding(
                modality="audio",
                signal_type=f"audio_scam:{_top_term(result.matched_terms)}",
                confidence=float(result.scam_probability),
                evidence={},  # "top_terms": _term_pairs(result.matched_terms),
            )
        ]

    def _run(self, video_path: Path):
        try:
            transcript = self._m.whisper.transcribe(video_path, self._m.transcripts_dir, force=False)
        except Exception:
            return None  # no speech / decode error -> no audio finding
        try:
            return self._m.keyword_detector.classify(transcript)
        except ValueError:
            return None

    async def explain(self, ctx: JobContext, findings: list[Finding]) -> Explanation | None:
        if not findings:
            return None
        return Explanation(
            scope="audio",
            method="keyword",
            attributions=_term_attrs(findings[0].evidence.get("top_terms", [])),
            summary=f"audio scam probability {findings[0].confidence:.2f}",
        )


class OcrScamPipeline:
    """On-screen text scam detection: OCR frames -> embedding vs scam profile."""

    name = "ocr_scam"
    modality = "ocr"
    whole_video = True

    def __init__(self, models: Models) -> None:
        self._m = models

    async def process(self, ctx: JobContext, unit: Unit) -> list[Finding]:
        if self._m.ocr_extractor is None or self._m.visual_embed is None:
            return []
        video_path = _video_path(ctx)
        if video_path is None:
            return []
        result = await asyncio.to_thread(self._run, video_path)
        if result is None:
            return []
        return [
            Finding(
                modality="ocr",
                signal_type=f"ocr_scam:{_top_term(result.matched_terms)}",
                confidence=float(result.scam_probability),
                evidence={
                    # "top_terms": _term_pairs(result.matched_terms),
                    "ocr_excerpt": (result.ocr_text or "")[:300],
                },
            )
        ]

    def _run(self, video_path: Path):
        ocr = self._m.ocr_extractor.extract(video_path)
        return self._m.visual_embed.classify(ocr)

    async def explain(self, ctx: JobContext, findings: list[Finding]) -> Explanation | None:
        if not findings:
            return None
        return Explanation(
            scope="ocr",
            method="embedding",
            attributions=_term_attrs(findings[0].evidence.get("top_terms", [])),
            summary=f"ocr scam probability {findings[0].confidence:.2f}",
        )


class CasinoClipPipeline:
    """Visual casino detection via CLIP zero-shot over sampled frames."""

    name = "casino_clip"
    modality = "visual"
    whole_video = True

    def __init__(self, models: Models) -> None:
        self._m = models

    async def process(self, ctx: JobContext, unit: Unit) -> list[Finding]:
        if self._m.clip is None:
            return []
        video_path = _video_path(ctx)
        if video_path is None:
            return []
        result = await asyncio.to_thread(self._run, video_path)
        if result is None:
            return []
        top = max(result.frame_predictions, key=lambda p: p.casino_probability) if result.frame_predictions else None
        return [
            Finding(
                modality="visual",
                signal_type="casino_visual",
                confidence=float(result.casino_probability),
                evidence={"top_prompt": top.top_prompt if top else "", "frames": result.analyzed_frames},
                ts_in_video=(top.timestamp_seconds if top else None),
            )
        ]

    def _run(self, video_path: Path):
        import casino_clip_detector as ccd

        return ccd.classify_file(detector=self._m.clip, path=video_path, video_frames=3, seed=42)

    async def explain(self, ctx: JobContext, findings: list[Finding]) -> Explanation | None:
        if not findings:
            return None
        finding = findings[0]
        return Explanation(
            scope="visual",
            method="clip",
            attributions=[Attribution(feature=finding.evidence.get("top_prompt", ""), value=1.0, weight=finding.confidence)],
            summary=f"casino visual probability {finding.confidence:.2f}",
        )


def build_real_registry(models: Models) -> PipelineRegistry:
    """Register the real model-backed pipelines (each no-ops if its model is absent)."""
    registry = PipelineRegistry()
    registry.register(WhisperKeywordTriage(models))
    registry.register(CaptionTextPipeline(models))
    registry.register(AudioScamPipeline(models))
    registry.register(OcrScamPipeline(models))
    registry.register(CasinoClipPipeline(models))
    return registry
