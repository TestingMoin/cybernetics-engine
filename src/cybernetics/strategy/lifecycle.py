from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Optional

class TradeLifecycleState(str, Enum):
    FLAT="FLAT"
    ENTRY_DECIDED="ENTRY_DECIDED"
    ENTRY_PENDING="ENTRY_PENDING"
    OPEN="OPEN"
    EXIT_DECIDED="EXIT_DECIDED"
    EXIT_PENDING="EXIT_PENDING"
    CLOSED="CLOSED"
    BLOCKED="BLOCKED"

@dataclass(frozen=True)
class StrategyTradeEvent:
    trade_id: str
    strategy_id: str
    underlying_key: str
    action: str
    state_before: TradeLifecycleState
    state_after: TradeLifecycleState
    signal_id: str
    rationale: str

class StrategyTradeLifecycle:
    """
    Strategy-side lifecycle only. It emits auditable intent events and never
    calls a broker or execution adapter.
    """
    def transition(self, *, trade_id: str, strategy_id: str,
                   underlying_key: str, current: TradeLifecycleState,
                   action: str, signal_id: str) -> StrategyTradeEvent:
        a=action.upper()
        if current==TradeLifecycleState.FLAT and a in {"ENTER_LONG","ENTER_SHORT"}:
            return StrategyTradeEvent(trade_id,strategy_id,underlying_key,a,current,
                TradeLifecycleState.ENTRY_DECIDED,signal_id,"entry_decision_created")
        if current==TradeLifecycleState.ENTRY_DECIDED and a.startswith("SUBMIT_"):
            return StrategyTradeEvent(trade_id,strategy_id,underlying_key,a,current,
                TradeLifecycleState.ENTRY_PENDING,signal_id,"entry_submission_requested")
        if current==TradeLifecycleState.ENTRY_PENDING and a=="FILL":
            return StrategyTradeEvent(trade_id,strategy_id,underlying_key,a,current,
                TradeLifecycleState.OPEN,signal_id,"entry_filled")
        if current==TradeLifecycleState.OPEN and a in {"EXIT_LONG","EXIT_SHORT","EXIT","STOP","TARGET"}:
            return StrategyTradeEvent(trade_id,strategy_id,underlying_key,a,current,
                TradeLifecycleState.EXIT_DECIDED,signal_id,"exit_decision_created")
        if current==TradeLifecycleState.EXIT_DECIDED and a=="SUBMIT_EXIT":
            return StrategyTradeEvent(trade_id,strategy_id,underlying_key,a,current,
                TradeLifecycleState.EXIT_PENDING,signal_id,"exit_submission_requested")
        if current==TradeLifecycleState.EXIT_PENDING and a=="FILL":
            return StrategyTradeEvent(trade_id,strategy_id,underlying_key,a,current,
                TradeLifecycleState.CLOSED,signal_id,"exit_filled")
        return StrategyTradeEvent(trade_id,strategy_id,underlying_key,a,current,
            TradeLifecycleState.BLOCKED,signal_id,"invalid_strategy_lifecycle_transition")

@dataclass
class LifecycleRecord:
    trade_id: str
    state: TradeLifecycleState

class StrategyLifecycleBook:
    def __init__(self):
        self._records: dict[str,LifecycleRecord]={}

    def state(self, trade_id:str)->TradeLifecycleState:
        rec=self._records.get(trade_id)
        return rec.state if rec else TradeLifecycleState.FLAT

    def apply(self,event:StrategyTradeEvent)->None:
        current=self.state(event.trade_id)
        if current != event.state_before:
            raise ValueError("lifecycle_state_conflict")
        if event.state_after==TradeLifecycleState.BLOCKED:
            raise ValueError("blocked_transition_cannot_be_applied")
        self._records[event.trade_id]=LifecycleRecord(event.trade_id,event.state_after)

    def clear(self,trade_id:str)->None:
        self._records.pop(trade_id,None)
