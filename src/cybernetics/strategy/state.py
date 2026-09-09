from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional, Any

class PositionState(str, Enum):
    FLAT="FLAT"
    LONG="LONG"
    SHORT="SHORT"

@dataclass(frozen=True)
class PositionSnapshot:
    underlying_key: str
    state: PositionState
    quantity: int = 0
    avg_price: Optional[float] = None

@dataclass(frozen=True)
class PositionAwareDecision:
    strategy_id: str
    signal_id: str
    underlying_key: str
    position_before: PositionState
    requested_action: str
    final_action: str
    rationale: str
    blocked: bool

class StrategyStateBook:
    """Small, deterministic state boundary. Persistence belongs to the ledger layer."""
    def __init__(self):
        self._positions: dict[str, PositionSnapshot] = {}

    def set_position(self, underlying_key: str, state: PositionState,
                     quantity: int = 0, avg_price: Optional[float] = None) -> None:
        if quantity < 0:
            raise ValueError("quantity_must_be_non_negative")
        if state == PositionState.FLAT and quantity != 0:
            raise ValueError("flat_position_requires_zero_quantity")
        if state != PositionState.FLAT and quantity == 0:
            raise ValueError("non_flat_position_requires_quantity")
        self._positions[underlying_key] = PositionSnapshot(
            underlying_key, state, quantity, avg_price
        )

    def get_position(self, underlying_key: str) -> PositionSnapshot:
        return self._positions.get(
            underlying_key, PositionSnapshot(underlying_key, PositionState.FLAT, 0, None)
        )

    def clear(self, underlying_key: str) -> None:
        self._positions.pop(underlying_key, None)

class PositionAwareDecisionEngine:
    """
    Applies position-state invariants AFTER strategy evaluation but BEFORE risk/
    execution. It never places, cancels, or modifies broker orders.
    """
    def __init__(self, state_book: StrategyStateBook):
        self.state_book = state_book

    def gate(self, *, strategy_id: str, signal_id: str,
             underlying_key: str, requested_action: str) -> PositionAwareDecision:
        pos = self.state_book.get_position(underlying_key)
        action = requested_action.upper()

        if action == "ENTER_LONG":
            if pos.state == PositionState.FLAT:
                return PositionAwareDecision(strategy_id, signal_id, underlying_key,
                    pos.state, action, action, "flat_allows_long_entry", False)
            if pos.state == PositionState.LONG:
                return PositionAwareDecision(strategy_id, signal_id, underlying_key,
                    pos.state, action, "HOLD", "already_long_duplicate_entry_blocked", True)
            return PositionAwareDecision(strategy_id, signal_id, underlying_key,
                pos.state, action, "NO_ACTION",
                "opposite_short_requires_explicit_reversal_workflow", True)

        if action == "ENTER_SHORT":
            if pos.state == PositionState.FLAT:
                return PositionAwareDecision(strategy_id, signal_id, underlying_key,
                    pos.state, action, action, "flat_allows_short_entry", False)
            if pos.state == PositionState.SHORT:
                return PositionAwareDecision(strategy_id, signal_id, underlying_key,
                    pos.state, action, "HOLD", "already_short_duplicate_entry_blocked", True)
            return PositionAwareDecision(strategy_id, signal_id, underlying_key,
                pos.state, action, "NO_ACTION",
                "opposite_long_requires_explicit_reversal_workflow", True)

        if action == "EXIT_LONG":
            if pos.state == PositionState.LONG:
                return PositionAwareDecision(strategy_id, signal_id, underlying_key,
                    pos.state, action, action, "long_position_exists_exit_allowed", False)
            return PositionAwareDecision(strategy_id, signal_id, underlying_key,
                pos.state, action, "NO_ACTION", "no_long_position_to_exit", True)

        if action == "EXIT_SHORT":
            if pos.state == PositionState.SHORT:
                return PositionAwareDecision(strategy_id, signal_id, underlying_key,
                    pos.state, action, action, "short_position_exists_exit_allowed", False)
            return PositionAwareDecision(strategy_id, signal_id, underlying_key,
                pos.state, action, "NO_ACTION", "no_short_position_to_exit", True)

        if action in {"HOLD", "NO_ACTION"}:
            return PositionAwareDecision(strategy_id, signal_id, underlying_key,
                pos.state, action, action, "non_entry_action_preserved", False)

        return PositionAwareDecision(strategy_id, signal_id, underlying_key,
            pos.state, action, "NO_ACTION", "unknown_action_blocked", True)
