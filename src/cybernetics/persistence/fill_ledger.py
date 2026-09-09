from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Protocol, Any


class FillLedgerState(str, Enum):
    CLAIMED = "CLAIMED"
    COMPLETED = "COMPLETED"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"


@dataclass(frozen=True)
class FillLedgerRecord:
    fill_id: str
    order_id: str
    trade_id: str
    state: FillLedgerState
    error: Optional[str] = None


class FillLedgerBackend(Protocol):
    """
    Minimal DB-transaction boundary expected from the PostgreSQL adapter.
    """

    def fetch_fill(self, fill_id: str) -> Optional[FillLedgerRecord]:
        ...

    def insert_claim(
        self,
        fill_id: str,
        order_id: str,
        trade_id: str,
    ) -> bool:
        ...

    def mark_completed(self, fill_id: str) -> None:
        ...

    def mark_recovery_required(self, fill_id: str, error: str) -> None:
        ...


class PostgreSQLFillLedger:
    """
    Durable fill idempotency/recovery boundary.

    This class deliberately receives a connection factory instead of owning a
    PostgreSQL pool. The production system should plug in the existing
    PostgreSQL infrastructure.

    Claim semantics:
      - INSERT succeeds -> caller owns the fill claim.
      - unique conflict -> caller must inspect existing state.
      - COMPLETED -> duplicate.
      - CLAIMED -> recovery required; do not replay.
      - RECOVERY_REQUIRED -> recovery workflow required.
    """

    CLAIM_SQL = """
        INSERT INTO fill_ledger
            (fill_id, order_id, trade_id, state)
        VALUES (%s, %s, %s, 'CLAIMED')
        ON CONFLICT (fill_id) DO NOTHING
    """

    FETCH_SQL = """
        SELECT fill_id, order_id, trade_id, state, error
        FROM fill_ledger
        WHERE fill_id = %s
    """

    COMPLETE_SQL = """
        UPDATE fill_ledger
        SET state = 'COMPLETED', error = NULL, completed_at = CURRENT_TIMESTAMP
        WHERE fill_id = %s AND state = 'CLAIMED'
    """

    RECOVERY_SQL = """
        UPDATE fill_ledger
        SET state = 'RECOVERY_REQUIRED', error = %s
        WHERE fill_id = %s AND state = 'CLAIMED'
    """

    def __init__(self, connection_factory):
        self.connection_factory = connection_factory

    def _row_to_record(self, row) -> Optional[FillLedgerRecord]:
        if row is None:
            return None
        fill_id, order_id, trade_id, state, error = row
        return FillLedgerRecord(
            str(fill_id),
            str(order_id),
            str(trade_id),
            FillLedgerState(str(state)),
            None if error is None else str(error),
        )

    def fetch_fill(self, fill_id: str) -> Optional[FillLedgerRecord]:
        with self.connection_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(self.FETCH_SQL, (fill_id,))
                return self._row_to_record(cur.fetchone())

    def insert_claim(self, fill_id: str, order_id: str, trade_id: str) -> bool:
        with self.connection_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(self.CLAIM_SQL, (fill_id, order_id, trade_id))
                inserted = cur.rowcount == 1
            conn.commit()
            return inserted

    def mark_completed(self, fill_id: str) -> None:
        with self.connection_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(self.COMPLETE_SQL, (fill_id,))
                if cur.rowcount != 1:
                    raise RuntimeError("fill_completion_conflict")
            conn.commit()

    def mark_recovery_required(self, fill_id: str, error: str) -> None:
        with self.connection_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(self.RECOVERY_SQL, (error, fill_id))
                if cur.rowcount != 1:
                    raise RuntimeError("fill_recovery_state_conflict")
            conn.commit()


from pathlib import Path

from cybernetics.db.schema import schema_path
_SCHEMA_PATH = schema_path()
FILL_LEDGER_DDL = _SCHEMA_PATH.read_text(encoding="utf-8") if _SCHEMA_PATH.is_file() else ""
