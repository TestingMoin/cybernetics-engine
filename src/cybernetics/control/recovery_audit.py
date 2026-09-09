from __future__ import annotations

from dataclasses import dataclass
from time import time
from typing import Any, Protocol


@dataclass(frozen=True)
class RecoveryAuditRecord:
    event_id: str
    event_type: str
    phase: str
    control_state: str
    emergency_state: str
    live_authorization_valid: bool
    failures: tuple[str, ...]
    reason: str
    actor: str
    event_ts: float


class Tx(Protocol):
    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> Any: ...


class ControlRecoveryAuditRepository:
    """Durable append-only audit boundary for control/recovery decisions."""

    def __init__(self, tx: Tx):
        self.tx = tx

    def append(self, record: RecoveryAuditRecord) -> None:
        self.tx.execute(
            """
            INSERT INTO control_recovery_audit(
                event_id, event_type, phase, control_state, emergency_state,
                live_authorization_valid, failures, reason, actor, event_ts
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,TO_TIMESTAMP(%s))
            ON CONFLICT (event_id) DO NOTHING
            """,
            (
                record.event_id,
                record.event_type,
                record.phase,
                record.control_state,
                record.emergency_state,
                record.live_authorization_valid,
                _json_array(record.failures),
                record.reason,
                record.actor,
                record.event_ts,
            ),
        )


def _json_array(values: tuple[str, ...]) -> str:
    import json
    return json.dumps(list(values), separators=(",", ":"))


def new_recovery_audit_record(
    *,
    event_id: str,
    event_type: str,
    phase: str,
    control_state: str,
    emergency_state: str,
    live_authorization_valid: bool,
    failures: tuple[str, ...] = (),
    reason: str,
    actor: str = "runtime",
    event_ts: float | None = None,
) -> RecoveryAuditRecord:
    return RecoveryAuditRecord(
        event_id=event_id,
        event_type=event_type,
        phase=phase,
        control_state=control_state,
        emergency_state=emergency_state,
        live_authorization_valid=live_authorization_valid,
        failures=failures,
        reason=reason,
        actor=actor,
        event_ts=time() if event_ts is None else event_ts,
    )


__all__ = ["RecoveryAuditRecord", "ControlRecoveryAuditRepository", "new_recovery_audit_record"]
