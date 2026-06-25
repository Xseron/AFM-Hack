"""Example checker plugin (auto-loaded): flags contact/redirect spam in captions.

Scam reels often push viewers off-platform ("write in telegram", "ссылка в шапке",
referral promo codes). This adds a cheap caption-level signal. Delete this file
(or remove the node on the Pipeline tab) to drop it.
"""
from __future__ import annotations

from app.pipelines.base import Finding, JobContext, Unit
from app.pipelines.explain import Attribution, Explanation

# Lowercased substring -> confidence contribution.
PATTERNS = {
    "telegram": 0.3,
    "телеграм": 0.3,
    "ссылка в шапке": 0.35,
    "link in bio": 0.3,
    "промокод": 0.3,
    "promo code": 0.25,
    "whatsapp": 0.25,
    "напиши в личку": 0.3,
    "dm me": 0.2,
}


class ContactSpamChecker:
    name = "contact_spam"
    modality = "text"

    async def process(self, ctx: JobContext, unit: Unit) -> list[Finding]:
        text = (unit.payload.get("text") or ctx.description or "").lower()
        return [
            Finding(
                modality=self.modality,
                signal_type=f"contact_spam:{phrase}",
                confidence=weight,
                evidence={"phrase": phrase},
            )
            for phrase, weight in PATTERNS.items()
            if phrase in text
        ]

    async def explain(self, ctx: JobContext, findings: list[Finding]) -> Explanation | None:
        if not findings:
            return None
        attrs = [Attribution(feature=f.evidence["phrase"], value=1.0, weight=f.confidence) for f in findings]
        return Explanation(
            scope="text",
            method="keyword",
            attributions=attrs,
            summary=f"{len(findings)} off-platform/contact spam phrase(s) in caption",
        )


PIPELINE = ContactSpamChecker()
