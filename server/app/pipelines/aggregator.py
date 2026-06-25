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

# Pipelines whose findings never decide the scam/semi-scam verdict. They are
# still recorded and shown, but a deepfake or off-platform-contact hit alone
# must not colour a reel red/yellow.
VERDICT_IGNORED_PIPELINES: frozenset[str] = frozenset({"deepfake_gend", "contact_spam"})

# A reel is "semi-scam" (yellow) when a checker reaches threshold/SEMI_SCAM_DIVISOR
# but not its full threshold; full threshold -> "scam" (red); otherwise "clean".
SEMI_SCAM_DIVISOR: float = 1.5

# Verdict tiers, returned by ``verdict_for`` and surfaced to the UI.
SCAM = "scam"
SEMI_SCAM = "semi_scam"
CLEAN = "clean"

_GAMBLING = ("казино", "ставк", "casino")
_PYRAMID = ("пирамид", "реферал", "инвест", "доход")


def threshold_for(name: str) -> float:
    return SCANNER_THRESHOLDS.get(name, DEFAULT_THRESHOLD)


def verdict_for(findings: list[Finding]) -> str:
    """Three-tier verdict from per-scanner thresholds.

    ``deepfake_gend`` and ``contact_spam`` are ignored here (see
    ``VERDICT_IGNORED_PIPELINES``). For every other finding we compare its
    confidence to its scanner threshold:

      * any finding >= threshold              -> ``SCAM``  (red)
      * else any finding >= threshold / 1.5   -> ``SEMI_SCAM`` (yellow)
      * else                                  -> ``CLEAN`` (green)
    """
    semi = False
    for f in findings:
        if _pipeline_of(f) in VERDICT_IGNORED_PIPELINES:
            continue
        th = threshold_for(_pipeline_of(f))
        if f.confidence >= th:
            return SCAM
        if f.confidence >= th / SEMI_SCAM_DIVISOR:
            semi = True
    return SEMI_SCAM if semi else CLEAN


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
    verdict = verdict_for(findings)
    scam = verdict == SCAM
    attrs: list[Attribution] = []
    for f in findings:
        th = threshold_for(_pipeline_of(f))
        # weight carries the threshold each finding was measured against.
        attrs.append(Attribution(feature=f"{f.modality}:{f.signal_type}", value=f.confidence, weight=th))
    category = _category(findings, scam)
    exp = Explanation(
        scope="aggregate",
        method="threshold",
        attributions=attrs,
        summary=f"risk={score:.2f} category={category} verdict={verdict} from {len(findings)} finding(s)",
    )
    return score, category, exp
