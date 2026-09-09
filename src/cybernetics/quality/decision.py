from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class Evidence:
    name: str
    direction: str
    strength: float
    required: bool = False

@dataclass(frozen=True)
class QualityDecision:
    accepted: bool
    score: float
    reasons: tuple[str, ...]
    direction: str
    evidence_used: tuple[str, ...]

class QualityEngine:
    """Evidence-aware quality gate. No broker execution."""
    def evaluate(self, *, direction: str, evidence: list[Evidence],
                 data_quality_ok: bool, strategy_approved: bool,
                 regime: Optional[str] = None, min_score: float = 0.60,
                 required_names: tuple[str, ...] = ()) -> QualityDecision:
        reasons = []
        if not data_quality_ok:
            reasons.append("data_quality_failed")
        if not strategy_approved:
            reasons.append("strategy_not_approved")
        if direction not in {"LONG", "SHORT"}:
            reasons.append("invalid_direction")

        used, aligned = [], []
        for e in evidence:
            if e.direction not in {"LONG", "SHORT", "NEUTRAL"}:
                continue
            if e.direction == direction:
                aligned.append(max(0.0, min(1.0, e.strength)))
                used.append(e.name)

        missing = [n for n in required_names if n not in used]
        if missing:
            reasons.append("missing_required_evidence:" + ",".join(missing))

        score = sum(aligned) / len(aligned) if aligned else 0.0
        if score < min_score:
            reasons.append("quality_score_below_threshold")
        if regime == "RANGE":
            score *= 0.90

        return QualityDecision(not reasons, score, tuple(reasons), direction, tuple(used))
