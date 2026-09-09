from __future__ import annotations
from dataclasses import dataclass
from .registry import SignalContext, SignalRegistry

@dataclass(frozen=True)
class SignalDecision:
    accepted: bool
    reasons: tuple[str, ...]
    signal_id: str

class SignalGateway:
    def __init__(self, registry: SignalRegistry):
        self.registry = registry

    def accept(self, signal: SignalContext, *, minimum_score: float = 0.0,
               minimum_confidence: float = 0.0) -> SignalDecision:
        reasons = []
        if signal.is_expired():
            reasons.append("expired")
        if not 0.0 <= signal.score <= 1.0:
            reasons.append("invalid_score")
        if not 0.0 <= signal.confidence <= 1.0:
            reasons.append("invalid_confidence")
        if signal.score < minimum_score:
            reasons.append("score_below_threshold")
        if signal.confidence < minimum_confidence:
            reasons.append("confidence_below_threshold")
        if not signal.instrument or not signal.underlying:
            reasons.append("missing_identity")
        accepted = not reasons
        if accepted:
            self.registry.publish(signal)
        return SignalDecision(accepted, tuple(reasons), signal.signal_id)
