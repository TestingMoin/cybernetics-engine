from __future__ import annotations

from typing import Any

from .outbox_worker import OutboxItem


class PostgresOutboxRepository:
    """
    PostgreSQL adapter for the outbox worker.

    The surrounding connection/pool lifecycle remains caller-owned. SQL is
    parameterized. Stale PROCESSING records are returned to PENDING so a
    crashed worker does not strand an event permanently.
    """

    def __init__(self, tx: Any):
        self.tx = tx

    def claim_outbox_batch(self, limit: int = 100) -> list[OutboxItem]:
        if limit <= 0:
            raise ValueError("limit_must_be_positive")

        rows = self.tx.fetchall(
            """
            WITH picked AS (
                SELECT event_id
                FROM fill_outbox
                WHERE state = 'PENDING'
                ORDER BY created_at, event_id
                FOR UPDATE SKIP LOCKED
                LIMIT %s
            )
            UPDATE fill_outbox o
            SET state = 'PROCESSING', attempts = o.attempts + 1
            FROM picked
            WHERE o.event_id = picked.event_id
            RETURNING o.event_id, o.fill_id, o.order_id, o.trade_id,
                      o.payload_json, o.attempts
            """,
            (limit,),
        )
        return [
            OutboxItem(
                event_id=row[0],
                fill_id=row[1],
                order_id=row[2],
                trade_id=row[3],
                payload=row[4],
                attempts=row[5],
            )
            for row in rows
        ]

    def complete_outbox(self, event_id: str) -> bool:
        result = self.tx.execute(
            """
            UPDATE fill_outbox
            SET state='COMPLETED',
                last_error=NULL,
                completed_at=CURRENT_TIMESTAMP
            WHERE event_id=%s AND state='PROCESSING'
            """,
            (event_id,),
        )
        return int(getattr(result, "rowcount", result)) == 1

    def fail_outbox(self, event_id: str, error: str) -> bool:
        # Failed events are durable and visible. A separate recovery policy can
        # explicitly requeue them; this worker never silently retries in-place.
        result = self.tx.execute(
            """
            UPDATE fill_outbox
            SET state='FAILED', last_error=%s
            WHERE event_id=%s AND state='PROCESSING'
            """,
            (error, event_id),
        )
        return int(getattr(result, "rowcount", result)) == 1

    def recover_stale_processing(self, max_age_seconds: int) -> int:
        if max_age_seconds <= 0:
            raise ValueError("max_age_seconds_must_be_positive")
        result = self.tx.execute(
            """
            UPDATE fill_outbox
            SET state='PENDING'
            WHERE state='PROCESSING'
              AND created_at < CURRENT_TIMESTAMP
                             - (%s * INTERVAL '1 second')
            """,
            (max_age_seconds,),
        )
        return int(getattr(result, "rowcount", result))

    def pending_count(self) -> int:
        row = self.tx.fetchone(
            "SELECT COUNT(*) FROM fill_outbox WHERE state='PENDING'"
        )
        return int(row[0])
