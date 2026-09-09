from __future__ import annotations

from .repository import CommandAuditRecord, ControlCommandRepository


class PostgresCommandIdStore:
    """
    Command-id store backed by the same control_command_audit table.
    """

    def __init__(self, repository: ControlCommandRepository):
        self.repository = repository

    def seen(self, command_id: str) -> bool:
        return self.repository.command_seen(command_id)

    def remember(self, command_id: str) -> None:
        # The gateway will normally follow this with a complete audit write.
        # This fallback keeps the idempotency operation durable on its own.
        self.repository.ensure_command_record(
            CommandAuditRecord(
                command_id=command_id,
                command="UNKNOWN",
                source="UNKNOWN",
                result=__import__(
                    "cybernetics.control.repository",
                    fromlist=["CommandRecordState"]
                ).CommandRecordState.REJECTED,
                state="UNKNOWN",
                reason="command_seen_marker",
                issued_at=0.0,
            )
        )


class PostgresAuditSink:
    def __init__(self, repository: ControlCommandRepository):
        self.repository = repository

    def record(self, **event):
        from .repository import CommandRecordState
        record = CommandAuditRecord(
            command_id=str(event["command_id"]),
            command=str(event["command"]),
            source=str(event["source"]),
            result=CommandRecordState(str(event["result"])),
            state=str(event["state"]),
            reason=str(event["reason"]),
            issued_at=float(event["issued_at"]),
        )
        # First writer wins, guaranteeing command-id uniqueness at DB level.
        if self.repository.ensure_command_record(record):
            return True
        return self.repository.record_result(record)
