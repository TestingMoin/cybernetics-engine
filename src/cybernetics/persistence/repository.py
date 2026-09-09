from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Protocol


class LedgerState(str, Enum):
    CLAIMED = "CLAIMED"
    COMPLETED = "COMPLETED"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"


class OutboxState(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class FillLedgerRecord:
    fill_id: str
    order_id: str
    trade_id: str
    state: LedgerState
    error: str | None = None


@dataclass(frozen=True)
class FillOutboxRecord:
    event_id: str
    fill_id: str
    order_id: str
    trade_id: str
    payload: Mapping[str, Any]
    state: OutboxState
    attempts: int = 0
    last_error: str | None = None


class Tx(Protocol):
    def fetchone(self, sql: str, params: tuple[Any, ...] = ()) -> Any: ...
    def fetchall(self, sql: str, params: tuple[Any, ...] = ()) -> list[Any]: ...
    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> Any: ...


class FillPersistenceRepository:
    """
    PostgreSQL repository boundary for Chunk 64/65 persistence.

    The caller owns the transaction. A production adapter should pass a real
    psycopg transaction/cursor wrapper here. SQL is parameterized throughout.
    """

    def __init__(self, tx: Tx):
        self.tx = tx

    def claim_fill(self, record: FillLedgerRecord) -> bool:
        row = self.tx.fetchone(
            """
            INSERT INTO fill_ledger(fill_id, order_id, trade_id, state, error)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (fill_id) DO NOTHING
            RETURNING fill_id
            """,
            (
                record.fill_id,
                record.order_id,
                record.trade_id,
                record.state.value,
                record.error,
            ),
        )
        return row is not None

    def get_fill(self, fill_id: str) -> FillLedgerRecord | None:
        row = self.tx.fetchone(
            """
            SELECT fill_id, order_id, trade_id, state, error
            FROM fill_ledger
            WHERE fill_id = %s
            """,
            (fill_id,),
        )
        if row is None:
            return None
        return FillLedgerRecord(
            fill_id=row[0], order_id=row[1], trade_id=row[2],
            state=LedgerState(row[3]), error=row[4]
        )

    def complete_fill(self, fill_id: str) -> bool:
        result = self.tx.execute(
            """
            UPDATE fill_ledger
            SET state = %s, error = NULL, completed_at = CURRENT_TIMESTAMP
            WHERE fill_id = %s AND state = %s
            """,
            (
                LedgerState.COMPLETED.value,
                fill_id,
                LedgerState.CLAIMED.value,
            ),
        )
        return _rowcount(result) == 1

    def mark_recovery_required(self, fill_id: str, error: str) -> bool:
        result = self.tx.execute(
            """
            UPDATE fill_ledger
            SET state = %s, error = %s
            WHERE fill_id = %s
              AND state IN (%s, %s)
            """,
            (
                LedgerState.RECOVERY_REQUIRED.value,
                error,
                fill_id,
                LedgerState.CLAIMED.value,
                LedgerState.RECOVERY_REQUIRED.value,
            ),
        )
        return _rowcount(result) == 1

    def enqueue_outbox(self, record: FillOutboxRecord) -> bool:
        import json
        row = self.tx.fetchone(
            """
            INSERT INTO fill_outbox(
                event_id, fill_id, order_id, trade_id, payload_json,
                state, attempts, last_error
            )
            VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, %s)
            ON CONFLICT (fill_id) DO NOTHING
            RETURNING event_id
            """,
            (
                record.event_id,
                record.fill_id,
                record.order_id,
                record.trade_id,
                json.dumps(dict(record.payload), sort_keys=True),
                record.state.value,
                record.attempts,
                record.last_error,
            ),
        )
        return row is not None

    def claim_outbox_batch(self, limit: int = 100) -> list[dict[str, Any]]:
        if limit <= 0:
            raise ValueError("limit_must_be_positive")
        rows = self.tx.fetchall(
            """
            WITH picked AS (
                SELECT event_id
                FROM fill_outbox
                WHERE state = %s
                ORDER BY created_at, event_id
                FOR UPDATE SKIP LOCKED
                LIMIT %s
            )
            UPDATE fill_outbox o
            SET state = %s, attempts = o.attempts + 1
            FROM picked
            WHERE o.event_id = picked.event_id
            RETURNING o.event_id, o.fill_id, o.order_id, o.trade_id,
                      o.payload_json, o.attempts
            """,
            (
                OutboxState.PENDING.value,
                limit,
                OutboxState.PROCESSING.value,
            ),
        )
        return list(rows)

    def complete_outbox(self, event_id: str) -> bool:
        result = self.tx.execute(
            """
            UPDATE fill_outbox
            SET state = %s, last_error = NULL, completed_at = CURRENT_TIMESTAMP
            WHERE event_id = %s AND state = %s
            """,
            (
                OutboxState.COMPLETED.value,
                event_id,
                OutboxState.PROCESSING.value,
            ),
        )
        return _rowcount(result) == 1

    def fail_outbox(self, event_id: str, error: str) -> bool:
        result = self.tx.execute(
            """
            UPDATE fill_outbox
            SET state = %s, last_error = %s
            WHERE event_id = %s AND state = %s
            """,
            (
                OutboxState.FAILED.value,
                error,
                event_id,
                OutboxState.PROCESSING.value,
            ),
        )
        return _rowcount(result) == 1


def _rowcount(result: Any) -> int:
    value = getattr(result, "rowcount", result)
    return int(value)
