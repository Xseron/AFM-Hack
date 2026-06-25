"""Template checker plugin. Copy to a name WITHOUT a leading underscore to load it.

Files starting with `_` are ignored by discovery, so this template ships inert.
"""
from __future__ import annotations

from app.pipelines.base import Finding, JobContext, Unit


class ExampleChecker:
    name = "example_checker"
    modality = "text"  # text | ocr | audio | visual | triage

    # Phrase -> confidence. Lowercased substring match against the caption.
    PATTERNS = {
        "promo code": 0.3,
        "telegram": 0.25,
        "dm me": 0.2,
    }

    async def process(self, ctx: JobContext, unit: Unit) -> list[Finding]:
        text = (unit.payload.get("text") or ctx.description or "").lower()
        return [
            Finding(
                modality=self.modality,
                signal_type=f"example:{phrase}",
                confidence=weight,
                evidence={"phrase": phrase},
            )
            for phrase, weight in self.PATTERNS.items()
            if phrase in text
        ]

    async def explain(self, ctx: JobContext, findings: list[Finding]):
        return None


PIPELINE = ExampleChecker()
