from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from typing import Any, Optional

class DecisionType(str, Enum):
    NO_ACTION="NO_ACTION"
    ENTER_LONG="ENTER_LONG"
    ENTER_SHORT="ENTER_SHORT"
    HOLD="HOLD"
    EXIT="EXIT"

@dataclass(frozen=True)
class StrategyContext:
    signal_id: str
    scanner_id: str
    underlying_key: str
    timeframe: str
    timestamp: datetime
    direction: Optional[str]
    strength: float
    evidence: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class StrategyDecision:
    decision_id: str
    strategy_id: str
    signal_id: str
    decision: DecisionType
    timestamp: datetime
    rationale: str
    confidence: float
    parameters: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.decision_id or not self.strategy_id or not self.signal_id:
            raise ValueError("strategy_decision_identity_required")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("strategy_confidence_out_of_range")

# Backward-compatible re-export; Golden-specific definitions live in golden_models.
from .golden_models import GoldenContext, GoldenDecision
