from __future__ import annotations

from app.pipelines.base import Finding
from app.pipelines.explain import Attribution, Explanation

MODALITY_WEIGHT: dict[str, float] = {
    "triage": 0.2,
    "text": 0.3,
    "ocr": 0.15,
    "audio": 0.2,
    "visual": 0.15,
}

_GAMBLING = ("казино", "ставк", "casino")
_PYRAMID = ("пирамид", "реферал", "инвест", "доход")


def _category(findings: list[Finding], score: float) -> str:
    # Scan signal_type AND evidence so all matched terms (not just the top one,
    # which is what lands in signal_type) influence categorization.
    blob = " ".join(f"{f.signal_type} {f.evidence}".lower() for f in findings)
    if any(k in blob for k in _GAMBLING):
        return "gambling"
    if any(k in blob for k in _PYRAMID):
        return "pyramid"
    return "fraud" if score >= 0.5 else "clean"


def aggregate(findings: list[Finding]) -> tuple[float, str, Explanation]:
    score = 0.0
    attrs: list[Attribution] = []
    for f in findings:
        contribution = MODALITY_WEIGHT.get(f.modality, 0.1) * f.confidence
        score += contribution
        attrs.append(Attribution(feature=f"{f.modality}:{f.signal_type}", value=f.confidence, weight=contribution))
    score = min(1.0, score)
    category = _category(findings, score)
    exp = Explanation(
        scope="aggregate",
        method="shap",
        attributions=attrs,
        summary=f"risk={score:.2f} category={category} from {len(findings)} finding(s)",
    )
    return score, category, exp
