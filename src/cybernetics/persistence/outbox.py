from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Protocol, Any
import json


class OutboxState(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class FillOutboxEvent:
    event_id: str
    fill_id: str
    order_id: str
    trade_id: str
    payload: dict[str, Any]
    state: OutboxState = OutboxState.PENDING
    attempts: int = 0
    last_error: Optional[str] = None


class OutboxBackend(Protocol):
    def insert_if_absent(self, event: FillOutboxEvent) -> bool: ...
    def claim(self, event_id: str) -> bool: ...
    def mark_completed(self, event_id: str) -> None: ...
    def mark_failed(self, event_id: str, error: str) -> None: ...
    def get(self, event_id: str) -> Optional[FillOutboxEvent]: ...


class PostgreSQLFillOutbox:
    """
    Durable outbox boundary for canonical fill events.

    The outbox gives the system a persistent event record that survives process
    restart. It intentionally does not claim distributed exactly-once delivery;
    consumers must remain idempotent using event_id/fill_id.
    """

    INSERT_SQL = """
        INSERT INTO fill_outbox
            (event_id, fill_id, order_id, trade_id, payload_json, state, attempts)
        VALUES (%s, %s, %s, %s, %s::jsonb, 'PENDING', 0)
        ON CONFLICT (event_id) DO NOTHING
    """

    CLAIM_SQL = """
        UPDATE fill_outbox
        SET state = 'PROCESSING',
            attempts = attempts + 1
        WHERE event_id = %s AND state = 'PENDING'
    """

    COMPLETE_SQL = """
        UPDATE fill_outbox
        SET state = 'COMPLETED', completed_at = CURRENT_TIMESTAMP
        WHERE event_id = %s AND state = 'PROCESSING'
    """

    FAIL_SQL = """
        UPDATE fill_outbox
        SET state = 'FAILED', last_error = %s
        WHERE event_id = %s AND state = 'PROCESSING'
    """

    GET_SQL = """
        SELECT event_id, fill_id, order_id, trade_id,
               payload_json, state, attempts, last_error
        FROM fill_outbox
        WHERE event_id = %s
    """

    def __init__(self, connection_factory):
        self.connection_factory = connection_factory

    def insert_if_absent(self, event: FillOutboxEvent) -> bool:
        payload_json = json.dumps(
            event.payload, separators=(",", ":"), sort_keys=True
        )
        with self.connection_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    self.INSERT_SQL,
                    (
                        event.event_id,
                        event.fill_id,
                        event.order_id,
                        event.trade_id,
                        payload_json,
                    ),
                )
                inserted = cur.rowcount == 1
            conn.commit()
            return inserted

    def claim(self, event_id: str) -> bool:
        with self.connection_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(self.CLAIM_SQL, (event_id,))
                claimed = cur.rowcount == 1
            conn.commit()
            return claimed

    def mark_completed(self, event_id: str) -> None:
        with self.connection_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(self.COMPLETE_SQL, (event_id,))
                if cur.rowcount != 1:
                    raise RuntimeError("outbox_completion_conflict")
            conn.commit()

    def mark_failed(self, event_id: str, error: str) -> None:
        with self.connection_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(self.FAIL_SQL, (error, event_id))
                if cur.rowcount != 1:
                    raise RuntimeError("outbox_failure_state_conflict")
            conn.commit()

    def get(self, event_id: str) -> Optional[FillOutboxEvent]:
        with self.connection_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(self.GET_SQL, (event_id,))
                row = cur.fetchone()

        if row is None:
            return None

        event_id, fill_id, order_id, trade_id, payload, state, attempts, last_error = row
        if isinstance(payload, str):
            payload = json.loads(payload)

        return FillOutboxEvent(
            event_id=str(event_id),
            fill_id=str(fill_id),
            order_id=str(order_id),
            trade_id=str(trade_id),
            payload=dict(payload),
            state=OutboxState(str(state)),
            attempts=int(attempts),
            last_error=None if last_error is None else str(last_error),
        )


from pathlib import Path

from cybernetics.db.schema import schema_path
_SCHEMA_PATH = schema_path()
FILL_OUTBOX_DDL = _SCHEMA_PATH.read_text(encoding="utf-8") if _SCHEMA_PATH.is_file() else ""


@dataclass(frozen=True)
class OutboxDispatchResult:
    state: str
    reason: str
    event_id: str


class OutboxDispatcher:
    """
    Idempotent dispatcher boundary.

    It claims one PENDING event, calls the injected consumer, then marks the
    event COMPLETED or FAILED. A failed event is not silently retried here.
    """

    def __init__(self, backend: OutboxBackend, consumer):
        self.backend = backend
        self.consumer = consumer

    def dispatch(self, event_id: str) -> OutboxDispatchResult:
        event = self.backend.get(event_id)
        if event is None:
            return OutboxDispatchResult("NOT_FOUND", "outbox_event_not_found", event_id)

        if event.state == OutboxState.COMPLETED:
            return OutboxDispatchResult("DUPLICATE", "outbox_already_completed", event_id)

        if event.state != OutboxState.PENDING:
            return OutboxDispatchResult(
                "RECOVERY_REQUIRED",
                f"outbox_state_requires_recovery:{event.state.value}",
                event_id,
            )

        if not self.backend.claim(event_id):
            return OutboxDispatchResult(
                "RECOVERY_REQUIRED", "outbox_claim_conflict", event_id
            )

        try:
            self.consumer(event)
        except Exception as exc:
            self.backend.mark_failed(
                event_id, f"{type(exc).__name__}:{exc}"
            )
            return OutboxDispatchResult(
                "FAILED", "consumer_failure_recorded", event_id
            )

        self.backend.mark_completed(event_id)
        return OutboxDispatchResult(
            "COMPLETED", "outbox_event_processed", event_id
        )
