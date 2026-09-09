from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol


class CommandRecordState(str, Enum):
    ACCEPTED = "ACCEPTED"
    DUPLICATE = "DUPLICATE"
    REJECTED = "REJECTED"
    STALE = "STALE"


@dataclass(frozen=True)
class CommandAuditRecord:
    command_id: str
    command: str
    source: str
    result: CommandRecordState
    state: str
    reason: str
    issued_at: float


class Tx(Protocol):
    def fetchone(self, sql: str, params: tuple[Any, ...] = ()) -> Any: ...
    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> Any: ...


class ControlCommandRepository:
    """
    PostgreSQL persistence boundary for control-command idempotency and audit.

    The repository is intentionally transaction-agnostic: callers own the
    connection and transaction context.
    """

    def __init__(self, tx: Tx):
        self.tx = tx

    def ensure_command_record(self, record: CommandAuditRecord) -> bool:
        row = self.tx.fetchone(
            """
            INSERT INTO control_command_audit(
                command_id, command, source, result, state, reason, issued_at
            )
            VALUES (%s,%s,%s,%s,%s,%s,TO_TIMESTAMP(%s))
            ON CONFLICT (command_id) DO NOTHING
            RETURNING command_id
            """,
            (
                record.command_id,
                record.command,
                record.source,
                record.result.value,
                record.state,
                record.reason,
                record.issued_at,
            ),
        )
        return row is not None

    def command_seen(self, command_id: str) -> bool:
        row = self.tx.fetchone(
            """
            SELECT command_id
            FROM control_command_audit
            WHERE command_id=%s
            LIMIT 1
            """,
            (command_id,),
        )
        return row is not None

    def record_result(self, record: CommandAuditRecord) -> bool:
        result = self.tx.execute(
            """
            UPDATE control_command_audit
            SET command=%s,
                source=%s,
                result=%s,
                state=%s,
                reason=%s,
                issued_at=TO_TIMESTAMP(%s)
            WHERE command_id=%s
            """,
            (
                record.command,
                record.source,
                record.result.value,
                record.state,
                record.reason,
                record.issued_at,
                record.command_id,
            ),
        )
        return int(getattr(result, "rowcount", result)) == 1
