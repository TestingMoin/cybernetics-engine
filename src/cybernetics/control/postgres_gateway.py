from __future__ import annotations

from dataclasses import dataclass

from .gateway import ControlCommand, CommandReceipt, CommandResult
from .repository import (
    CommandAuditRecord,
    CommandRecordState,
    ControlCommandRepository,
)


@dataclass(frozen=True)
class DurableCommandStatus:
    command_id: str
    persisted: bool
    result: str
    state: str | None = None
    reason: str | None = None


class PostgresControlCommandGateway:
    """
    Durable composition wrapper around the control command gateway.

    The durable command-id boundary is consulted BEFORE the wrapped gateway.
    Therefore a command replay after a process/VPS restart cannot re-enter the
    state machine merely because the in-memory duplicate set was lost.

    The wrapper does not create live authorization and never calls broker order
    endpoints.
    """

    def __init__(self, gateway, connection_factory):
        self.gateway = gateway
        self.connection_factory = connection_factory

    def _read_existing(self, tx, command_id: str):
        return tx.fetchone(
            """
            SELECT command_id, result, state, reason
            FROM control_command_audit
            WHERE command_id=%s
            """,
            (command_id,),
        )

    @staticmethod
    def _enum_result(value: str) -> CommandResult:
        return CommandResult(value)

    def handle(self, cmd: ControlCommand, *, policy=None) -> CommandReceipt:
        # Durable duplicate check MUST precede state-machine execution.
        with self.connection_factory() as tx:
            existing = self._read_existing(tx, cmd.command_id)

        if existing is not None:
            _, result, state, reason = existing
            return CommandReceipt(
                command_id=cmd.command_id,
                result=self._enum_result(str(result)),
                state=__import__(
                    "cybernetics.runtime.control",
                    fromlist=["ControlState"]
                ).ControlState(str(state)),
                reason=str(reason),
            )

        receipt = self.gateway.handle(cmd, policy=policy)

        with self.connection_factory() as tx:
            repo = ControlCommandRepository(tx)
            record = CommandAuditRecord(
                command_id=cmd.command_id,
                command=cmd.command.value,
                source=cmd.source,
                result=CommandRecordState(receipt.result.value),
                state=receipt.state.value,
                reason=receipt.reason,
                issued_at=cmd.issued_at,
            )
            # DB uniqueness remains the final duplicate boundary.
            if not repo.ensure_command_record(record):
                existing = self._read_existing(tx, cmd.command_id)
                if existing is not None:
                    _, result, state, reason = existing
                    return CommandReceipt(
                        command_id=cmd.command_id,
                        result=self._enum_result(str(result)),
                        state=__import__(
                            "cybernetics.runtime.control",
                            fromlist=["ControlState"]
                        ).ControlState(str(state)),
                        reason=str(reason),
                    )
                repo.record_result(record)

        return receipt

    def durable_status(self, command_id: str) -> DurableCommandStatus:
        with self.connection_factory() as tx:
            row = self._read_existing(tx, command_id)

        if row is None:
            return DurableCommandStatus(command_id, False, "NOT_FOUND")

        _, result, state, reason = row
        return DurableCommandStatus(
            command_id=command_id,
            persisted=True,
            result=str(result),
            state=str(state),
            reason=str(reason),
        )
