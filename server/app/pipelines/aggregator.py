from __future__ import annotations

from app.pipelines.base import Finding
from app.pipelines.explain import Attribution, Explanation

# A reel is flagged as scam when any single checker's confidence reaches its
# threshold ("if scanner value >= threshold -> scam"). Thresholds are per
# pipeline (keyed by name); DEFAULT_THRESHOLD applies to any checker without an
# explicit one. Both are mutated live from the Pipeline tab
# (see app.pipelines.architecture) and at startup from MW_SCAM_THRESHOLD, so
# edit the values in place rather than rebinding names elsewhere.
DEFAULT_THRESHOLD: float = 0.5
SCANNER_THRESHOLDS: dict[str, float] = {}

_GAMBLING = ("казино", "ставк", "casino")
_PYRAMID = ("пирамид", "реферал", "инвест", "доход")


def threshold_for(name: str) -> float:
    return SCANNER_THRESHOLDS.get(name, DEFAULT_THRESHOLD)


def _pipeline_of(finding: Finding) -> str:
    return (finding.evidence or {}).get("_pipeline", "")


def _evidence_text(evidence: dict) -> str:
    # Skip the bookkeeping key so a pipeline name can't leak into categorization.
    return " ".join(f"{k}={v}" for k, v in (evidence or {}).items() if k != "_pipeline")


def _category(findings: list[Finding], scam: bool) -> str:
    if not scam:
        return "clean"
    # Scan signal_type AND evidence so all matched terms influence the label.
    blob = " ".join(f"{f.signal_type} {_evidence_text(f.evidence)}".lower() for f in findings)
    if any(k in blob for k in _GAMBLING):
        return "gambling"
    if any(k in blob for k in _PYRAMID):
        return "pyramid"
    return "fraud"


def aggregate(findings: list[Finding]) -> tuple[float, str, Explanation]:
    score = min(1.0, max((f.confidence for f in findings), default=0.0))
    scam = False
    attrs: list[Attribution] = []
    for f in findings:
        th = threshold_for(_pipeline_of(f))
        scam = scam or f.confidence >= th
        # weight carries the threshold each finding was measured against.
        attrs.append(Attribution(feature=f"{f.modality}:{f.signal_type}", value=f.confidence, weight=th))
    category = _category(findings, scam)
    exp = Explanation(
        scope="aggregate",
        method="threshold",
        attributions=attrs,
        summary=f"risk={score:.2f} category={category} scam={scam} from {len(findings)} finding(s)",
    )
    return score, category, exp
