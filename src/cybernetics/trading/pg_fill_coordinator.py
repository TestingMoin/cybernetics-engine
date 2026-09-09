from __future__ import annotations

from dataclasses import dataclass

from cybernetics.persistence.fill_ledger import (
    FillLedgerState, PostgreSQLFillLedger
)


@dataclass(frozen=True)
class DurableFillCoordinatorResult:
    state: str
    reason: str
    fill_id: str


class DurableFillCoordinator:
    """
    Persistent counterpart to the Chunk 63 reference coordinator.

    The ledger claim is durable and survives process restart. This class does
    not pretend that independent external systems form one ACID transaction;
    downstream failures are recorded for explicit recovery.
    """

    def __init__(self, ledger: PostgreSQLFillLedger, order_sink, position_sink, lifecycle_sink):
        self.ledger = ledger
        self.order_sink = order_sink
        self.position_sink = position_sink
        self.lifecycle_sink = lifecycle_sink

    def apply(self, fill) -> DurableFillCoordinatorResult:
        existing = self.ledger.fetch_fill(fill.fill_id)
        if existing is not None:
            if existing.state == FillLedgerState.COMPLETED:
                return DurableFillCoordinatorResult(
                    "DUPLICATE", "fill_already_completed", fill.fill_id
                )
            return DurableFillCoordinatorResult(
                "RECOVERY_REQUIRED",
                f"fill_requires_recovery:{existing.state.value}",
                fill.fill_id,
            )

        claimed = self.ledger.insert_claim(
            fill.fill_id, fill.order_id, fill.trade_id
        )
        if not claimed:
            existing = self.ledger.fetch_fill(fill.fill_id)
            if existing and existing.state == FillLedgerState.COMPLETED:
                return DurableFillCoordinatorResult(
                    "DUPLICATE", "fill_already_completed", fill.fill_id
                )
            return DurableFillCoordinatorResult(
                "RECOVERY_REQUIRED",
                "durable_claim_conflict",
                fill.fill_id,
            )

        try:
            self.order_sink.mark_fill_applied(fill)
            self.position_sink.apply_fill(fill)
            self.lifecycle_sink.on_fill(fill)
        except Exception as exc:
            self.ledger.mark_recovery_required(
                fill.fill_id, f"{type(exc).__name__}:{exc}"
            )
            return DurableFillCoordinatorResult(
                "RECOVERY_REQUIRED",
                "downstream_failure_recorded",
                fill.fill_id,
            )

        self.ledger.mark_completed(fill.fill_id)
        return DurableFillCoordinatorResult(
            "APPLIED",
            "durable_fill_application_completed",
            fill.fill_id,
        )
