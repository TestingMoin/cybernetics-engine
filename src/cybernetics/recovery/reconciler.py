from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Protocol


class RecoveryState(str, Enum):
    REQUIRED = "RECOVERY_REQUIRED"
    IN_PROGRESS = "RECOVERY_IN_PROGRESS"
    RESOLVED = "RECOVERY_RESOLVED"
    BLOCKED = "RECOVERY_BLOCKED"


class ReconcileDisposition(str, Enum):
    CONSISTENT = "CONSISTENT"
    BROKER_AHEAD = "BROKER_AHEAD"
    INTERNAL_AHEAD = "INTERNAL_AHEAD"
    MISSING_BROKER = "MISSING_BROKER"
    MISSING_INTERNAL = "MISSING_INTERNAL"
    CONFLICT = "CONFLICT"


@dataclass(frozen=True)
class RecoveryCase:
    recovery_id: str
    fill_id: str
    order_id: str
    trade_id: str
    reason: str
    state: RecoveryState = RecoveryState.REQUIRED


@dataclass(frozen=True)
class StateSnapshot:
    quantity: int
    side: str
    average_price: float


@dataclass(frozen=True)
class ReconciliationResult:
    disposition: ReconcileDisposition
    reason: str
    safe_to_resume_new_trades: bool


class BrokerRecoveryGateway(Protocol):
    def get_order(self, order_id: str) -> Mapping[str, object] | None: ...
    def get_positions(self) -> Mapping[str, StateSnapshot]: ...


class RecoveryCaseStore(Protocol):
    def save_required(self, case: RecoveryCase) -> None: ...
    def mark_in_progress(self, recovery_id: str) -> None: ...
    def mark_resolved(self, recovery_id: str) -> None: ...
    def mark_blocked(self, recovery_id: str, reason: str) -> None: ...
    def list_open(self) -> list[RecoveryCase]: ...


class FillRecoveryCoordinator:
    """
    Controlled recovery boundary.

    Recovery never submits a new order. It first reconciles broker/internal
    state and only marks a case RESOLVED when the caller's reconciliation
    evidence is consistent. Any ambiguity remains BLOCKED.
    """

    def __init__(
        self,
        store: RecoveryCaseStore,
        broker: BrokerRecoveryGateway,
    ):
        self.store = store
        self.broker = broker

    def register(self, case: RecoveryCase) -> None:
        self.store.save_required(case)

    @staticmethod
    def compare_positions(
        internal: StateSnapshot | None,
        broker: StateSnapshot | None,
        *,
        quantity_tolerance: int = 0,
        price_tolerance: float = 0.01,
    ) -> ReconciliationResult:
        if internal is None and broker is None:
            return ReconciliationResult(
                ReconcileDisposition.CONSISTENT,
                "position_absent_on_both_sides",
                True,
            )
        if internal is None:
            return ReconciliationResult(
                ReconcileDisposition.BROKER_AHEAD,
                "broker_has_position_internal_missing",
                False,
            )
        if broker is None:
            return ReconciliationResult(
                ReconcileDisposition.INTERNAL_AHEAD,
                "internal_has_position_broker_missing",
                False,
            )
        if internal.side != broker.side:
            return ReconciliationResult(
                ReconcileDisposition.CONFLICT,
                "position_side_mismatch",
                False,
            )
        if abs(internal.quantity - broker.quantity) > quantity_tolerance:
            return ReconciliationResult(
                ReconcileDisposition.CONFLICT,
                "position_quantity_mismatch",
                False,
            )
        if abs(internal.average_price - broker.average_price) > price_tolerance:
            return ReconciliationResult(
                ReconcileDisposition.CONFLICT,
                "position_average_price_mismatch",
                False,
            )
        return ReconciliationResult(
            ReconcileDisposition.CONSISTENT,
            "position_consistent",
            True,
        )

    def recover_case(
        self,
        case: RecoveryCase,
        *,
        internal_order: Mapping[str, object] | None,
        internal_position: StateSnapshot | None,
        security_id: str,
    ) -> ReconciliationResult:
        self.store.mark_in_progress(case.recovery_id)

        broker_order = self.broker.get_order(case.order_id)
        broker_positions = self.broker.get_positions()
        broker_position = broker_positions.get(security_id)

        # Order existence/status is intentionally evidence only. This boundary
        # never submits, replaces, or cancels an order during recovery.
        if broker_order is None:
            self.store.mark_blocked(
                case.recovery_id,
                "broker_order_not_found_during_recovery",
            )
            return ReconciliationResult(
                ReconcileDisposition.MISSING_BROKER,
                "broker_order_not_found_during_recovery",
                False,
            )

        result = self.compare_positions(internal_position, broker_position)
        if result.disposition is ReconcileDisposition.CONSISTENT:
            self.store.mark_resolved(case.recovery_id)
            return result

        self.store.mark_blocked(case.recovery_id, result.reason)
        return result
