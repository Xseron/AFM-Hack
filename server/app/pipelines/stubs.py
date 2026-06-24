from __future__ import annotations

from app.pipelines.base import Finding, JobContext, Unit
from app.pipelines.explain import Attribution, Explanation
from app.pipelines.registry import PipelineRegistry

# Shared risk lexicon (substring -> weight). Lowercased matching.
PATTERNS: dict[str, float] = {
    "казино": 0.5,
    "casino": 0.5,
    "ставк": 0.4,
    "гарантированн": 0.45,
    "доход": 0.3,
    "инвест": 0.3,
    "реферал": 0.35,
    "бонус": 0.2,
    "пирамид": 0.5,
}


def _matched(text: str) -> list[tuple[str, float]]:
    low = text.lower()
    return [(kw, w) for kw, w in PATTERNS.items() if kw in low]


class TriageClassifier:
    name = "triage_keyword"
    modality = "triage"

    async def process(self, ctx: JobContext, unit: Unit) -> list[Finding]:
        text = unit.payload.get("text", "")
        return [
            Finding(modality="triage", signal_type=f"keyword:{kw}", confidence=w, evidence={"keyword": kw})
            for kw, w in _matched(text)
        ]

    async def explain(self, ctx: JobContext, findings: list[Finding]) -> Explanation | None:
        if not findings:
            return None
        attrs = [Attribution(feature=f.evidence["keyword"], value=1.0, weight=f.confidence) for f in findings]
        return Explanation(
            scope="triage",
            method="feature_importance",
            attributions=attrs,
            summary=f"{len(findings)} risk keyword(s) matched in description",
        )


class TextPipeline:
    name = "text_nlp"
    modality = "text"

    async def process(self, ctx: JobContext, unit: Unit) -> list[Finding]:
        text = unit.payload.get("text", "")
        return [
            Finding(modality="text", signal_type=f"text_signal:{kw}", confidence=w, evidence={"keyword": kw})
            for kw, w in _matched(text)
        ]

    async def explain(self, ctx: JobContext, findings: list[Finding]) -> Explanation | None:
        if not findings:
            return None
        attrs = [Attribution(feature=f.evidence["keyword"], value=1.0, weight=f.confidence) for f in findings]
        return Explanation(
            scope="text",
            method="shap",
            attributions=attrs,
            summary="Token-level contributions (stub SHAP)",
        )


class OCRPipeline:
    name = "ocr_text"
    modality = "ocr"

    async def process(self, ctx: JobContext, unit: Unit) -> list[Finding]:
        if unit.index != 0:
            return []
        low = ctx.description.lower()
        if any(ch.isdigit() for ch in low) or "%" in low:
            return [Finding(modality="ocr", signal_type="on_screen_number", confidence=0.3,
                            evidence={"note": "numeric/percent marker (stub)"}, ts_in_video=0.0)]
        return []

    async def explain(self, ctx: JobContext, findings: list[Finding]) -> Explanation | None:
        if not findings:
            return None
        return Explanation(scope="ocr", method="lime", attributions=[], summary="OCR region attribution (stub)")


class AudioPipeline:
    name = "audio_asr"
    modality = "audio"

    async def process(self, ctx: JobContext, unit: Unit) -> list[Finding]:
        if unit.index != 0:
            return []
        if "доход" in ctx.description.lower():
            return [Finding(modality="audio", signal_type="speech_promise", confidence=0.4,
                            evidence={"transcript": "(stub) обещание дохода"}, ts_in_video=unit.payload.get("ts"))]
        return []

    async def explain(self, ctx: JobContext, findings: list[Finding]) -> Explanation | None:
        if not findings:
            return None
        return Explanation(scope="audio", method="shap", attributions=[], summary="ASR token attribution (stub)")


class VisualPipeline:
    name = "visual_cv"
    modality = "visual"

    async def process(self, ctx: JobContext, unit: Unit) -> list[Finding]:
        if unit.index != 0:
            return []
        low = ctx.description.lower()
        if "казино" in low or "casino" in low:
            return [Finding(modality="visual", signal_type="casino_marker", confidence=0.45,
                            evidence={"note": "casino visual marker (stub)"}, ts_in_video=0.0)]
        return []

    async def explain(self, ctx: JobContext, findings: list[Finding]) -> Explanation | None:
        if not findings:
            return None
        return Explanation(scope="visual", method="gradcam", attributions=[], summary="Saliency over frame (stub)")


def register_default_pipelines(registry: PipelineRegistry) -> PipelineRegistry:
    for p in (TriageClassifier(), TextPipeline(), OCRPipeline(), AudioPipeline(), VisualPipeline()):
        registry.register(p)
    return registry


def build_registry(enabled_names: list[str] | None = None) -> PipelineRegistry:
    """Build a registry, optionally limited to the named pipelines (config-driven).

    ``enabled_names`` falsy -> register all defaults; otherwise only those whose
    ``name`` is listed. This is how `MW_ENABLED_PIPELINES` selects active pipelines.
    """
    registry = PipelineRegistry()
    for p in (TriageClassifier(), TextPipeline(), OCRPipeline(), AudioPipeline(), VisualPipeline()):
        if not enabled_names or p.name in enabled_names:
            registry.register(p)
    return registry
