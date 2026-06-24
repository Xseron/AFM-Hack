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


class SemanticPriorityPipeline:
    """Fast priority signal: caption text -> scam vocabulary/embedding alignment.

    This intentionally runs before OCR/CLIP/audio. It uses the same scam lexicons
    as the audio and OCR systems, but does not decode the video.
    """

    name = "semantic_priority"
    modality = "triage"
    whole_video = True

    def __init__(self, models: Models) -> None:
        self._m = models

    async def process(self, ctx: JobContext, unit: Unit) -> list[Finding]:
        text = (ctx.description or "").strip()
        if not text:
            return []
        result = await asyncio.to_thread(self._classify, text)
        if result is None:
            return []
        confidence, evidence = result
        return [
            Finding(
                modality="triage",
                signal_type="semantic_scam_alignment",
                confidence=float(confidence),
                evidence=evidence,
            )
        ]

    def _classify(self, text: str):
        import audio_detect as ad
        import scam_image_detector as sid

        keyword_probability = 0.0
        keyword_terms: list[list] = []
        if self._m.keyword_detector is not None:
            transcript = ad.Transcript(video_path=Path("<caption>"), text_path=Path("<none>"), text=text)
            try:
                keyword_result = self._m.keyword_detector.classify(transcript)
                keyword_probability = float(keyword_result.scam_probability)
                keyword_terms = _term_pairs(keyword_result.matched_terms)
            except ValueError:
                pass

        semantic_probability = 0.0
        semantic_terms: list[list] = []
        scam_similarity = 0.0
        clean_similarity = 0.0
        normalized_text = ""
        if self._m.visual_embed is not None:
            ocr_like_text = sid.normalize_text(text)
            normalized_text = ocr_like_text
            ocr = sid.OcrResult(
                source_path=Path("<caption>"),
                text_path=Path("<none>"),
                text=ocr_like_text,
                frame_count=0,
            )
            semantic_result = self._m.visual_embed.classify(ocr)
            semantic_probability = float(semantic_result.scam_probability)
            semantic_terms = _term_pairs(semantic_result.matched_terms)
            scam_similarity = float(semantic_result.scam_similarity)
            clean_similarity = float(semantic_result.clean_similarity)

        confidence = max(keyword_probability, semantic_probability)
        evidence = {
            "source": "description",
            "keyword_probability": keyword_probability,
            "semantic_probability": semantic_probability,
            "scam_similarity": scam_similarity,
            "clean_similarity": clean_similarity,
            "keyword_top_terms": keyword_terms,
            "semantic_top_terms": semantic_terms,
            "normalized_excerpt": normalized_text[:300],
        }
        return confidence, evidence

    async def explain(self, ctx: JobContext, findings: list[Finding]) -> Explanation | None:
        if not findings:
            return None
        evidence = findings[0].evidence
        attrs = _term_attrs(evidence.get("semantic_top_terms", []) or evidence.get("keyword_top_terms", []))
        return Explanation(
            scope="semantic_priority",
            method="lexicon_embedding_alignment",
            attributions=attrs,
            summary=f"semantic priority score {findings[0].confidence:.2f}",
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
                evidence={"top_terms": _term_pairs(result.matched_terms)},
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
        scored = await asyncio.to_thread(self._run, video_path)
        if scored is None:
            return []
        ocr, result, normalized_text = scored
        top_terms = _term_pairs(result.matched_terms)
        has_semantic_signal = (
            bool(result.matched_terms)
            or result.predicted_label == "scam"
            or result.scam_similarity > result.clean_similarity + 0.03
        )
        confidence = float(result.scam_probability) if has_semantic_signal else 0.0
        signal_type = (
            f"ocr_scam:{_top_term(result.matched_terms)}"
            if has_semantic_signal
            else "ocr_text_low_signal"
        )
        evidence = {
            "ocr_excerpt": (ocr.text or "")[:300],
            "normalized_ocr_excerpt": normalized_text[:300],
            "top_terms": top_terms,
            "scam_similarity": result.scam_similarity,
            "clean_similarity": result.clean_similarity,
            "keyword_score": result.keyword_score,
            "frame_count": result.frame_count,
            "semantic_checked": has_semantic_signal,
        }
        return [
            Finding(
                modality="ocr",
                signal_type=signal_type,
                confidence=confidence,
                evidence=evidence,
            )
        ]

    def _run(self, video_path: Path):
        import scam_image_detector as sid

        ocr = self._m.ocr_extractor.extract(video_path)
        result = self._m.visual_embed.classify(ocr)
        return ocr, result, sid.normalize_text(ocr.text)

    async def explain(self, ctx: JobContext, findings: list[Finding]) -> Explanation | None:
        if not findings:
            return None
        if not findings[0].evidence.get("semantic_checked"):
            return Explanation(
                scope="ocr",
                method="quality_gate",
                attributions=[],
                summary="OCR text extracted, but semantic scam signal was too weak to score as risk",
            )
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
    registry.register(SemanticPriorityPipeline(models))
    registry.register(AudioScamPipeline(models))
    registry.register(OcrScamPipeline(models))
    registry.register(CasinoClipPipeline(models))
    return registry
