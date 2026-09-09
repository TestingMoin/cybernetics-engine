from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Any

from cybernetics.risk.handoff import (
    RiskAction, RiskHandoffResult, StrategyRiskHandoff
)


@dataclass(frozen=True)
class StrategyDecisionInput:
    strategy_id: str
    strategy_version: str
    signal_id: str
    trade_id: str
    underlying_key: str
    timeframe: str
    action: str
    timestamp: datetime
    entry_reference_price: Optional[float] = None
    stop_reference_price: Optional[float] = None
    target_reference_price: Optional[float] = None
    metadata: dict[str, Any] | None = None


class StrategyToRiskAdapter:
    """
    Converts a strategy decision into the canonical risk request contract.
    It does not calculate quantity and does not call the execution layer.
    """

    def __init__(self, handoff: StrategyRiskHandoff):
        self.handoff = handoff

    def adapt(self, decision: StrategyDecisionInput) -> RiskHandoffResult:
        return self.handoff.create_request(
            strategy_id=decision.strategy_id,
            strategy_version=decision.strategy_version,
            signal_id=decision.signal_id,
            trade_id=decision.trade_id,
            underlying_key=decision.underlying_key,
            timeframe=decision.timeframe,
            action=decision.action,
            timestamp=decision.timestamp,
            entry_reference_price=decision.entry_reference_price,
            stop_reference_price=decision.stop_reference_price,
            target_reference_price=decision.target_reference_price,
            metadata=decision.metadata,
        )
