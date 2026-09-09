from __future__ import annotations
from typing import Optional
from cybernetics.order_management.idempotency import IdempotencyRecord

class PostgresOrderLedger:
    """
    PostgreSQL boundary for durable idempotency.

    The SQL uses a UNIQUE client_order_key constraint. The actual database
    driver/connection pool is injected, keeping credentials and DB lifecycle
    outside this module.
    """
    UPSERT_SQL = """
    INSERT INTO order_idempotency (client_order_key, broker_order_id, status)
    VALUES (%s, %s, %s)
    ON CONFLICT (client_order_key) DO NOTHING
    """

    SELECT_SQL = """
    SELECT client_order_key, broker_order_id, status
    FROM order_idempotency
    WHERE client_order_key = %s
    """

    UPDATE_SQL = """
    UPDATE order_idempotency
    SET broker_order_id = %s, status = %s
    WHERE client_order_key = %s
    """

    def __init__(self, connection):
        self._connection = connection

    def get(self, key: str) -> Optional[IdempotencyRecord]:
        cur = self._connection.cursor()
        try:
            cur.execute(self.SELECT_SQL, (key,))
            row = cur.fetchone()
            if row is None:
                return None
            return IdempotencyRecord(row[0], row[1], row[2])
        finally:
            cur.close()

    def put_once(self, record: IdempotencyRecord) -> bool:
        cur = self._connection.cursor()
        try:
            cur.execute(
                self.UPSERT_SQL,
                (record.client_order_key, record.broker_order_id, record.status),
            )
            inserted = cur.rowcount == 1
            self._connection.commit()
            return inserted
        except Exception:
            self._connection.rollback()
            raise
        finally:
            cur.close()

    def update(self, record: IdempotencyRecord) -> None:
        cur = self._connection.cursor()
        try:
            cur.execute(
                self.UPDATE_SQL,
                (record.broker_order_id, record.status, record.client_order_key),
            )
            if cur.rowcount != 1:
                raise KeyError("unknown_client_order_key")
            self._connection.commit()
        except Exception:
            self._connection.rollback()
            raise
        finally:
            cur.close()
