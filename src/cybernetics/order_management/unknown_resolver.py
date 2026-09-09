from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Protocol

from .idempotency import IdempotencyRecord, IdempotencyBackend

class ResolutionState(str, Enum):
    RESOLVED_ACCEPTED = "RESOLVED_ACCEPTED"
    RESOLVED_REJECTED = "RESOLVED_REJECTED"
    STILL_UNKNOWN = "STILL_UNKNOWN"
    AMBIGUOUS = "AMBIGUOUS"

@dataclass(frozen=True)
class ResolutionResult:
    state: ResolutionState
    client_order_key: str
    broker_order_id: Optional[str]
    message: str

class OrderLookup(Protocol):
    def get_orders(self) -> list[dict]: ...

class UnknownOrderResolver:
    """
    Safely resolves client-side UNKNOWN orders.

    Rule: only an exact broker-returned client_order_key match is bindable.
    No fuzzy symbol/side/quantity matching is permitted here.
    """
    def __init__(self, broker: OrderLookup, store: IdempotencyBackend):
        self._broker = broker
        self._store = store

    def resolve(self, client_order_key: str) -> ResolutionResult:
        current = self._store.get(client_order_key)
        if current is None:
            return ResolutionResult(
                ResolutionState.STILL_UNKNOWN, client_order_key, None,
                "client_order_key_not_registered"
            )

        if current.status != "UNKNOWN":
            return self._from_record(current)

        candidates = [
            row for row in self._broker.get_orders()
            if row.get("client_order_key") == client_order_key
        ]

        if len(candidates) == 0:
            return ResolutionResult(
                ResolutionState.STILL_UNKNOWN, client_order_key, None,
                "broker_has_no_exact_client_key_match"
            )

        if len(candidates) != 1:
            return ResolutionResult(
                ResolutionState.AMBIGUOUS, client_order_key, None,
                "multiple_exact_client_key_matches"
            )

        row = candidates[0]
        broker_id = row.get("broker_order_id")
        status = str(row.get("status","")).upper()

        if not broker_id:
            return ResolutionResult(
                ResolutionState.STILL_UNKNOWN, client_order_key, None,
                "broker_match_has_no_order_id"
            )

        if status in {"ACCEPTED","OPEN","PARTIAL","FILLED"}:
            self._store.update(
                IdempotencyRecord(client_order_key, broker_id, "ACCEPTED")
            )
            return ResolutionResult(
                ResolutionState.RESOLVED_ACCEPTED, client_order_key, broker_id,
                "exact_broker_match_bound"
            )

        if status in {"REJECTED","CANCELLED","EXPIRED"}:
            self._store.update(
                IdempotencyRecord(client_order_key, broker_id, status)
            )
            return ResolutionResult(
                ResolutionState.RESOLVED_REJECTED, client_order_key, broker_id,
                f"broker_status_{status.lower()}"
            )

        return ResolutionResult(
            ResolutionState.STILL_UNKNOWN, client_order_key, broker_id,
            f"unrecognized_or_pending_broker_status:{status}"
        )

    @staticmethod
    def _from_record(record: IdempotencyRecord) -> ResolutionResult:
        if record.status == "ACCEPTED":
            return ResolutionResult(
                ResolutionState.RESOLVED_ACCEPTED,
                record.client_order_key, record.broker_order_id,
                "already_resolved"
            )
        if record.status in {"REJECTED","CANCELLED","EXPIRED"}:
            return ResolutionResult(
                ResolutionState.RESOLVED_REJECTED,
                record.client_order_key, record.broker_order_id,
                "already_resolved_rejected"
            )
        return ResolutionResult(
            ResolutionState.STILL_UNKNOWN,
            record.client_order_key, record.broker_order_id,
            "record_not_resolved"
        )
