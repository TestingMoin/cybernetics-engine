from __future__ import annotations
from dataclasses import dataclass
from typing import Callable

from .models import StrategyContext, StrategyDecision, DecisionType

@dataclass(frozen=True)
class StrategyDefinition:
    strategy_id: str
    version: str
    evaluate: Callable[[StrategyContext], StrategyDecision]

class StrategyEngine:
    """
    Deterministic strategy integration boundary.

    The engine receives an already-qualified signal context and delegates the
    actual strategy rule to a versioned StrategyDefinition.

    A strategy decision is informational and auditable; it is not an order.
    """
    def __init__(self):
        self._strategies: dict[str, StrategyDefinition] = {}

    def register(self, definition: StrategyDefinition) -> None:
        if not definition.strategy_id or not definition.version:
            raise ValueError("strategy_identity_required")
        if definition.strategy_id in self._strategies:
            raise ValueError("strategy_already_registered")
        self._strategies[definition.strategy_id] = definition

    def get(self, strategy_id: str) -> StrategyDefinition:
        try:
            return self._strategies[strategy_id]
        except KeyError:
            raise KeyError("strategy_not_found")

    def evaluate(self, strategy_id: str, context: StrategyContext) -> StrategyDecision:
        strategy = self.get(strategy_id)
        decision = strategy.evaluate(context)
        if decision.strategy_id != strategy_id:
            raise ValueError("strategy_decision_strategy_id_mismatch")
        if decision.signal_id != context.signal_id:
            raise ValueError("strategy_decision_signal_id_mismatch")
        return decision

    def all(self) -> list[StrategyDefinition]:
        return list(self._strategies.values())

def deterministic_direction_strategy(strategy_id: str, version: str = "1.0.0"):
    """
    Minimal integration strategy used for framework tests only.

    It maps an already-qualified signal direction into ENTER_LONG/ENTER_SHORT.
    No indicator combination is introduced here.
    """
    def evaluate(ctx: StrategyContext) -> StrategyDecision:
        if ctx.direction == "BUY":
            decision = DecisionType.ENTER_LONG
            rationale = "qualified_buy_signal"
        elif ctx.direction == "SELL":
            decision = DecisionType.ENTER_SHORT
            rationale = "qualified_sell_signal"
        else:
            decision = DecisionType.NO_ACTION
            rationale = "unsupported_signal_direction"

        return StrategyDecision(
            decision_id=f"{strategy_id}:{ctx.signal_id}",
            strategy_id=strategy_id,
            signal_id=ctx.signal_id,
            decision=decision,
            timestamp=ctx.timestamp,
            rationale=rationale,
            confidence=ctx.strength,
            parameters={},
        )

    return StrategyDefinition(strategy_id, version, evaluate)
