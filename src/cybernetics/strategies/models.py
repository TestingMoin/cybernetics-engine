from __future__ import annotations
from dataclasses import dataclass
from typing import Literal, Optional

Side = Literal["LONG", "SHORT", "FLAT"]
StrategyAction = Literal["ENTER_LONG", "ENTER_SHORT", "EXIT", "HOLD", "WAIT"]

@dataclass(frozen=True)
class StrategyContext:
    timestamp: float
    symbol: str
    timeframe: str
    close: float
    month: int
    position_side: Side = "FLAT"
    position_avg_price: Optional[float] = None

@dataclass(frozen=True)
class StrategyDecision:
    strategy_id: str
    action: StrategyAction
    reason: str
    side: Side = "FLAT"
    stop_price: Optional[float] = None
    target_price: Optional[float] = None
    metadata: dict = None

    def __post_init__(self):
        if self.metadata is None:
            object.__setattr__(self, "metadata", {})
