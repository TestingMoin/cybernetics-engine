from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol


class UnifiedFillState(str, Enum):
    ACCEPTED = "ACCEPTED"
    DUPLICATE = "DUPLICATE"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class CanonicalFillRecord:
    fill_id: str
    order_id: str
    trade_id: str
    underlying_key: str
    side: str
    quantity: int
    price: float
    fee: float = 0.0
    broker_timestamp: str | None = None


@dataclass(frozen=True)
class UnifiedFillResult:
    state: UnifiedFillState
    reason: str
    fill_id: str


class FillDurability(Protocol):
    def status(self, fill_id: str) -> str | None: ...
    def claim(self, fill: CanonicalFillRecord) -> bool: ...
    def complete(self, fill_id: str) -> None: ...
    def recover(self, fill_id: str, error: str) -> None: ...


class OrderConsumer(Protocol):
    def apply(self, fill: CanonicalFillRecord) -> None: ...


class PositionConsumer(Protocol):
    def apply(self, fill: CanonicalFillRecord) -> None: ...


class LifecycleConsumer(Protocol):
    def apply(self, fill: CanonicalFillRecord) -> None: ...


class UnifiedFillProcessor:
    """
    Canonical single-entry fill-processing boundary.

    Every broker fill should enter here exactly once at the application
    boundary. The processor uses durable fill state to prevent duplicate
    application and sequences all downstream consumers consistently.

    This provides deterministic at-least-once processing with recovery.
    It does not claim a distributed ACID transaction across all consumers.
    """

    def __init__(
        self,
        *,
        durability: FillDurability,
        order_consumer: OrderConsumer,
        position_consumer: PositionConsumer,
        lifecycle_consumer: LifecycleConsumer,
    ):
        self.durability = durability
        self.order_consumer = order_consumer
        self.position_consumer = position_consumer
        self.lifecycle_consumer = lifecycle_consumer

    def process(self, fill: CanonicalFillRecord) -> UnifiedFillResult:
        invalid = self._validate(fill)
        if invalid:
            return UnifiedFillResult(
                UnifiedFillState.BLOCKED, invalid, fill.fill_id or "INVALID"
            )

        current = self.durability.status(fill.fill_id)

        if current == "COMPLETED":
            return UnifiedFillResult(
                UnifiedFillState.DUPLICATE, "fill_already_completed", fill.fill_id
            )

        if current in {"CLAIMED", "PROCESSING", "RECOVERY_REQUIRED"}:
            return UnifiedFillResult(
                UnifiedFillState.RECOVERY_REQUIRED,
                f"fill_state_requires_recovery:{current}",
                fill.fill_id,
            )

        if not self.durability.claim(fill):
            current = self.durability.status(fill.fill_id)
            if current == "COMPLETED":
                return UnifiedFillResult(
                    UnifiedFillState.DUPLICATE,
                    "fill_already_completed",
                    fill.fill_id,
                )
            return UnifiedFillResult(
                UnifiedFillState.RECOVERY_REQUIRED,
                "durable_fill_claim_conflict",
                fill.fill_id,
            )

        try:
            # Fixed, auditable application order.
            self.order_consumer.apply(fill)
            self.position_consumer.apply(fill)
            self.lifecycle_consumer.apply(fill)
        except Exception as exc:
            self.durability.recover(
                fill.fill_id, f"{type(exc).__name__}:{exc}"
            )
            return UnifiedFillResult(
                UnifiedFillState.RECOVERY_REQUIRED,
                "downstream_failure_recorded",
                fill.fill_id,
            )

        try:
            self.durability.complete(fill.fill_id)
        except Exception as exc:
            # Downstream state may already be applied. Never replay blindly.
            self.durability.recover(
                fill.fill_id, f"completion_failure:{type(exc).__name__}:{exc}"
            )
            return UnifiedFillResult(
                UnifiedFillState.RECOVERY_REQUIRED,
                "durable_completion_failed",
                fill.fill_id,
            )

        return UnifiedFillResult(
            UnifiedFillState.ACCEPTED,
            "canonical_fill_processed",
            fill.fill_id,
        )

    @staticmethod
    def _validate(fill: CanonicalFillRecord) -> str | None:
        if not fill.fill_id or not fill.order_id or not fill.trade_id:
            return "fill_identity_required"
        if not fill.underlying_key:
            return "underlying_required"
        if fill.side.upper() not in {"BUY", "SELL"}:
            return "unsupported_fill_side"
        if fill.quantity <= 0:
            return "fill_quantity_must_be_positive"
        if fill.price <= 0:
            return "fill_price_must_be_positive"
        if fill.fee < 0:
            return "fill_fee_must_be_non_negative"
        return None


class InMemoryDurability:
    """Reference durability implementation used only for isolated tests."""

    def __init__(self):
        self.states: dict[str, str] = {}
        self.errors: dict[str, str] = {}
        self.claim_log: list[str] = []

    def status(self, fill_id: str) -> str | None:
        return self.states.get(fill_id)

    def claim(self, fill: CanonicalFillRecord) -> bool:
        if fill.fill_id in self.states:
            return False
        self.states[fill.fill_id] = "CLAIMED"
        self.claim_log.append(fill.fill_id)
        return True

    def complete(self, fill_id: str) -> None:
        if self.states.get(fill_id) != "CLAIMED":
            raise RuntimeError("completion_state_invalid")
        self.states[fill_id] = "COMPLETED"

    def recover(self, fill_id: str, error: str) -> None:
        if fill_id not in self.states:
            raise RuntimeError("recovery_fill_not_claimed")
        self.states[fill_id] = "RECOVERY_REQUIRED"
        self.errors[fill_id] = error
