from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class ExitPlan:
    symbol: str
    side: str
    entry_price: float
    stop_price: Optional[float] = None
    target_price: Optional[float] = None
    trailing_distance: Optional[float] = None

@dataclass(frozen=True)
class ExitDecision:
    should_exit: bool
    reason: str
    trigger_price: Optional[float]

class ExitManager:
    """Independent exit-condition evaluator. It returns decisions; it does not execute."""
    def evaluate(self, plan: ExitPlan, last_price: float) -> ExitDecision:
        if last_price <= 0:
            return ExitDecision(False,"invalid_price",None)
        if plan.side=="LONG":
            if plan.stop_price is not None and last_price <= plan.stop_price:
                return ExitDecision(True,"STOP_LOSS",last_price)
            if plan.target_price is not None and last_price >= plan.target_price:
                return ExitDecision(True,"TAKE_PROFIT",last_price)
        elif plan.side=="SHORT":
            if plan.stop_price is not None and last_price >= plan.stop_price:
                return ExitDecision(True,"STOP_LOSS",last_price)
            if plan.target_price is not None and last_price <= plan.target_price:
                return ExitDecision(True,"TAKE_PROFIT",last_price)
        else:
            return ExitDecision(False,"invalid_side",None)
        return ExitDecision(False,"HOLD",None)
