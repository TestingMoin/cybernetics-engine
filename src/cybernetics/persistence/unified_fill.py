from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Mapping

from .repository import (
    FillLedgerRecord, FillOutboxRecord, FillPersistenceRepository,
    LedgerState, OutboxState,
)
from .transaction import atomic_fill_transaction


class FillResult(str, Enum):
    COMPLETED = "COMPLETED"
    DUPLICATE_COMPLETED = "DUPLICATE_COMPLETED"
    DUPLICATE_IN_PROGRESS = "DUPLICATE_IN_PROGRESS"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"
    INVALID = "INVALID"


@dataclass(frozen=True)
class CanonicalFillRecord:
    fill_id: str
    order_id: str
    trade_id: str
    security_id: str
    side: str
    quantity: int
    price: float
    timestamp: str
    payload: Mapping[str, Any]


class UnifiedFillProcessorPostgres:
    """
    Durable replacement for the temporary in-memory fill-durability boundary.

    Order, Position, and Trade-Lifecycle handlers are injected callbacks.
    They are called only after durable CLAIMED state exists. Any processing
    exception is converted into durable RECOVERY_REQUIRED state inside the
    transaction. A successful path enqueues exactly one outbox event by fill_id
    before marking the ledger COMPLETED.
    """

    def __init__(
        self,
        connection: Any,
        *,
        repository_factory: Callable[[Any], FillPersistenceRepository]
        = FillPersistenceRepository,
    ):
        self.connection = connection
        self.repository_factory = repository_factory

    @staticmethod
    def _validate(fill: CanonicalFillRecord) -> None:
        if not fill.fill_id or not fill.order_id or not fill.trade_id:
            raise ValueError("fill_identity_required")
        if not fill.security_id:
            raise ValueError("security_id_required")
        if fill.quantity <= 0:
            raise ValueError("fill_quantity_must_be_positive")
        if fill.price <= 0:
            raise ValueError("fill_price_must_be_positive")
        if fill.side not in {"BUY", "SELL"}:
            raise ValueError("fill_side_invalid")

    def process(
        self,
        fill: CanonicalFillRecord,
        *,
        apply_order: Callable[[CanonicalFillRecord], None],
        apply_position: Callable[[CanonicalFillRecord], None],
        apply_lifecycle: Callable[[CanonicalFillRecord], None],
        event_id: str,
    ) -> FillResult:
        try:
            self._validate(fill)
        except ValueError:
            return FillResult.INVALID

        try:
            with atomic_fill_transaction(self.connection) as tx:
                repo = self.repository_factory(tx)

                claimed = repo.claim_fill(
                    FillLedgerRecord(
                        fill_id=fill.fill_id,
                        order_id=fill.order_id,
                        trade_id=fill.trade_id,
                        state=LedgerState.CLAIMED,
                    )
                )

                if not claimed:
                    existing = repo.get_fill(fill.fill_id)
                    if existing is None:
                        raise RuntimeError("claim_conflict_but_fill_missing")
                    if existing.state is LedgerState.COMPLETED:
                        return FillResult.DUPLICATE_COMPLETED
                    if existing.state is LedgerState.RECOVERY_REQUIRED:
                        return FillResult.RECOVERY_REQUIRED
                    return FillResult.DUPLICATE_IN_PROGRESS

                try:
                    apply_order(fill)
                    apply_position(fill)
                    apply_lifecycle(fill)

                    repo.enqueue_outbox(
                        FillOutboxRecord(
                            event_id=event_id,
                            fill_id=fill.fill_id,
                            order_id=fill.order_id,
                            trade_id=fill.trade_id,
                            payload=dict(fill.payload),
                            state=OutboxState.PENDING,
                        )
                    )

                    if not repo.complete_fill(fill.fill_id):
                        raise RuntimeError("fill_completion_failed")

                except Exception as exc:
                    repo.mark_recovery_required(
                        fill.fill_id, f"{type(exc).__name__}: {exc}"
                    )
                    return FillResult.RECOVERY_REQUIRED

                return FillResult.COMPLETED

        except Exception:
            # Transaction/persistence failure means durable completion is unknown.
            # The caller must reconcile; no blind retry is performed here.
            return FillResult.RECOVERY_REQUIRED
