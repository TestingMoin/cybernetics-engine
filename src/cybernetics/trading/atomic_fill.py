from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol, Optional


class FillApplicationState(str, Enum):
    APPLIED = "APPLIED"
    DUPLICATE = "DUPLICATE"
    BLOCKED = "BLOCKED"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"


@dataclass(frozen=True)
class CanonicalFill:
    fill_id: str
    order_id: str
    trade_id: str
    underlying_key: str
    side: str
    quantity: int
    price: float
    fee: float = 0.0


@dataclass(frozen=True)
class FillCoordinatorResult:
    state: FillApplicationState
    reason: str
    fill_id: str


class FillSink(Protocol):
    def apply_fill(self, fill: CanonicalFill):
        ...


class OrderFillSink(Protocol):
    def mark_fill_applied(self, fill: CanonicalFill):
        ...


class TradeLifecycleSink(Protocol):
    def on_fill(self, fill: CanonicalFill):
        ...


class FillApplicationCoordinator:
    """
    Coordinates one canonical fill across order, position and trade-lifecycle
    boundaries.

    True distributed atomicity requires a shared transactional event/ledger
    mechanism. This coordinator therefore uses an explicit two-phase pattern:
      1) claim fill ID
      2) apply downstream mutations
      3) mark completion

    A failure after claim produces RECOVERY_REQUIRED rather than silently
    replaying the fill. Production persistence should implement claim/complete
    atomically in PostgreSQL.
    """

    def __init__(
        self,
        *,
        fill_registry,
        order_sink: OrderFillSink,
        position_sink: FillSink,
        lifecycle_sink: TradeLifecycleSink,
    ):
        self.fill_registry = fill_registry
        self.order_sink = order_sink
        self.position_sink = position_sink
        self.lifecycle_sink = lifecycle_sink

    def apply(self, fill: CanonicalFill) -> FillCoordinatorResult:
        if not fill.fill_id or not fill.order_id or not fill.trade_id:
            return FillCoordinatorResult(
                FillApplicationState.BLOCKED,
                "fill_identity_required",
                fill.fill_id or "INVALID",
            )
        if fill.quantity <= 0 or fill.price <= 0:
            return FillCoordinatorResult(
                FillApplicationState.BLOCKED,
                "fill_quantity_price_invalid",
                fill.fill_id,
            )

        status = self.fill_registry.status(fill.fill_id)
        if status == "COMPLETED":
            return FillCoordinatorResult(
                FillApplicationState.DUPLICATE,
                "fill_already_completed",
                fill.fill_id,
            )
        if status == "CLAIMED":
            return FillCoordinatorResult(
                FillApplicationState.RECOVERY_REQUIRED,
                "fill_claimed_but_not_completed",
                fill.fill_id,
            )

        if not self.fill_registry.claim(fill.fill_id, fill.order_id, fill.trade_id):
            current = self.fill_registry.status(fill.fill_id)
            if current == "COMPLETED":
                return FillCoordinatorResult(
                    FillApplicationState.DUPLICATE,
                    "fill_already_completed",
                    fill.fill_id,
                )
            return FillCoordinatorResult(
                FillApplicationState.RECOVERY_REQUIRED,
                "fill_claim_failed",
                fill.fill_id,
            )

        try:
            self.order_sink.mark_fill_applied(fill)
            self.position_sink.apply_fill(fill)
            self.lifecycle_sink.on_fill(fill)
        except Exception as exc:
            self.fill_registry.mark_recovery_required(fill.fill_id, str(exc))
            return FillCoordinatorResult(
                FillApplicationState.RECOVERY_REQUIRED,
                f"downstream_failure:{type(exc).__name__}",
                fill.fill_id,
            )

        self.fill_registry.complete(fill.fill_id)
        return FillCoordinatorResult(
            FillApplicationState.APPLIED,
            "fill_applied_to_all_downstream_boundaries",
            fill.fill_id,
        )


class InMemoryFillRegistry:
    """
    Test/reference registry. Production should replace this with the persistent
    PostgreSQL transaction boundary.
    """

    def __init__(self):
        self._status = {}
        self._error = {}

    def status(self, fill_id: str):
        return self._status.get(fill_id)

    def claim(self, fill_id: str, order_id: str, trade_id: str):
        if fill_id in self._status:
            return False
        self._status[fill_id] = "CLAIMED"
        return True

    def complete(self, fill_id: str):
        self._status[fill_id] = "COMPLETED"

    def mark_recovery_required(self, fill_id: str, error: str):
        self._status[fill_id] = "RECOVERY_REQUIRED"
        self._error[fill_id] = error

    def error(self, fill_id: str):
        return self._error.get(fill_id)
