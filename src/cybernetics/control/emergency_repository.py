from __future__ import annotations

from typing import Any
from pathlib import Path

from cybernetics.db.schema import schema_path


class PostgresEmergencyRepository:
    """
    PostgreSQL persistence for the emergency latch.

    A singleton row (`control_key='GLOBAL'`) is used so there is exactly one
    durable emergency state for this engine instance.
    """

    _SCHEMA_PATH = schema_path()
    DDL = _SCHEMA_PATH.read_text(encoding="utf-8") if _SCHEMA_PATH.is_file() else ""

    def __init__(self, tx: Any):
        self.tx = tx

    def load_active(self):
        row = self.tx.fetchone(
            """
            SELECT active, emergency_id, reason, actor,
                   EXTRACT(EPOCH FROM issued_at)
            FROM emergency_control_state
            WHERE control_key='GLOBAL'
            """,
        )
        if row is None or not row[0]:
            return None

        from .emergency import EmergencyState, EmergencyStatus
        return EmergencyStatus(
            EmergencyState.ACTIVE,
            row[1], row[2], row[3],
            float(row[4]) if row[4] is not None else None,
        )

    def persist_trip(self, record):
        self.tx.execute(
            """
            INSERT INTO emergency_control_state(
                control_key, active, emergency_id, reason, actor, issued_at
            )
            VALUES ('GLOBAL', TRUE, %s, %s, %s, TO_TIMESTAMP(%s))
            ON CONFLICT (control_key)
            DO UPDATE SET active=TRUE,
                          emergency_id=EXCLUDED.emergency_id,
                          reason=EXCLUDED.reason,
                          actor=EXCLUDED.actor,
                          issued_at=EXCLUDED.issued_at,
                          updated_at=CURRENT_TIMESTAMP
            """,
            (
                record.emergency_id, record.reason,
                record.actor, record.issued_at
            ),
        )

    def persist_clear(self, emergency_id: str, actor: str, issued_at: float):
        result = self.tx.execute(
            """
            UPDATE emergency_control_state
            SET active=FALSE,
                emergency_id=NULL,
                reason=NULL,
                actor=%s,
                issued_at=TO_TIMESTAMP(%s),
                updated_at=CURRENT_TIMESTAMP
            WHERE control_key='GLOBAL'
              AND active=TRUE
              AND emergency_id=%s
            """,
            (actor, issued_at, emergency_id),
        )
        if int(getattr(result, "rowcount", result)) != 1:
            raise ValueError("emergency_clear_not_persisted")
