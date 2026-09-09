from __future__ import annotations
from dataclasses import dataclass
from cybernetics.strategy.lifecycle import (
    StrategyTradeLifecycle, StrategyLifecycleBook, TradeLifecycleState, StrategyTradeEvent
)

@dataclass(frozen=True)
class LifecycleBridgeResult:
    accepted: bool
    reason: str
    event: StrategyTradeEvent

class StrategyPositionLifecycleBridge:
    """
    Bridges strategy decisions to lifecycle intent and existing position-aware
    state without performing execution. Entry/exit submission remains an
    external responsibility of the execution pipeline.
    """
    def __init__(self,lifecycle:StrategyTradeLifecycle,book:StrategyLifecycleBook):
        self.lifecycle=lifecycle
        self.book=book

    def apply_decision(self, *, trade_id:str, strategy_id:str,
                       underlying_key:str, signal_id:str, action:str)->LifecycleBridgeResult:
        current=self.book.state(trade_id)
        event=self.lifecycle.transition(
            trade_id=trade_id,strategy_id=strategy_id,
            underlying_key=underlying_key,current=current,
            action=action,signal_id=signal_id)
        if event.state_after==TradeLifecycleState.BLOCKED:
            return LifecycleBridgeResult(False,event.rationale,event)
        self.book.apply(event)
        return LifecycleBridgeResult(True,"lifecycle_transition_accepted",event)
