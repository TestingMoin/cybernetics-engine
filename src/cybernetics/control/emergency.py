from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol


class EmergencyState(str, Enum):
    CLEAR = "CLEAR"
    ACTIVE = "ACTIVE"


class EmergencyAction(str, Enum):
    TRIP = "TRIP"
    RESTORE_FOR_RECOVERY = "RESTORE_FOR_RECOVERY"


@dataclass(frozen=True)
class EmergencyRecord:
    emergency_id: str
    action: EmergencyAction
    reason: str
    actor: str
    issued_at: float


@dataclass(frozen=True)
class EmergencyStatus:
    state: EmergencyState
    emergency_id: str | None
    reason: str | None
    actor: str | None
    issued_at: float | None


class EmergencyPersistence(Protocol):
    def load_active(self) -> EmergencyStatus | None: ...
    def persist_trip(self, record: EmergencyRecord) -> None: ...
    def persist_clear(self, emergency_id: str, actor: str, issued_at: float) -> None: ...


class DurableEmergencyStop:
    """
    Persistent emergency-stop latch.

    The latch is conservative:
    - TRIP is idempotent for the same emergency_id.
    - An ACTIVE emergency remains ACTIVE until an explicit recovery/restore
      operation is persisted.
    - There is no automatic clear during process startup.
    """

    def __init__(self, persistence: EmergencyPersistence):
        self.persistence = persistence
        self._status = EmergencyStatus(EmergencyState.CLEAR, None, None, None, None)

    @property
    def status(self) -> EmergencyStatus:
        return self._status

    def restore_on_startup(self) -> EmergencyStatus:
        persisted = self.persistence.load_active()
        if persisted is not None:
            self._status = persisted
        else:
            self._status = EmergencyStatus(
                EmergencyState.CLEAR, None, None, None, None
            )
        return self._status

    def trip(self, record: EmergencyRecord) -> EmergencyStatus:
        if not record.emergency_id:
            raise ValueError("emergency_id_required")
        if not record.reason:
            raise ValueError("emergency_reason_required")
        if not record.actor:
            raise ValueError("emergency_actor_required")

        if (
            self._status.state is EmergencyState.ACTIVE
            and self._status.emergency_id == record.emergency_id
        ):
            return self._status

        self.persistence.persist_trip(record)
        self._status = EmergencyStatus(
            EmergencyState.ACTIVE,
            record.emergency_id,
            record.reason,
            record.actor,
            record.issued_at,
        )
        return self._status

    def restore_for_recovery(
        self,
        *,
        emergency_id: str,
        actor: str,
        issued_at: float,
    ) -> EmergencyStatus:
        if self._status.state is not EmergencyState.ACTIVE:
            raise ValueError("emergency_not_active")
        if emergency_id != self._status.emergency_id:
            raise ValueError("emergency_id_mismatch")
        if not actor:
            raise ValueError("recovery_actor_required")

        self.persistence.persist_clear(emergency_id, actor, issued_at)
        self._status = EmergencyStatus(
            EmergencyState.CLEAR, None, None, None, None
        )
        return self._status
