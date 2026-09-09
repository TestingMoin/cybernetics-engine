from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping

from cybernetics.control.recovery_audit import (
    ControlRecoveryAuditRepository,
    new_recovery_audit_record,
)
from .control_recovery import ControlRecoveryIntegration, ControlRecoverySnapshot
from .state import EmergencyState


@dataclass(frozen=True)
class PersistentRecoveryEvent:
    event_id: str
    event_type: str
    phase: str
    reason: str


class PersistentControlRecoveryIntegration:
    """Durably records control/recovery observations and explicit resumes.

    Persistence is an audit side effect only. Recovery/control decisions still
    flow through the authoritative in-memory state machine and guards.
    """

    def __init__(
        self,
        integration: ControlRecoveryIntegration,
        connection_factory: Callable[[], object],
        event_id_factory: Callable[[], str],
    ) -> None:
        self.integration = integration
        self.connection_factory = connection_factory
        self.event_id_factory = event_id_factory

    def _persist(self, *, event_type: str, event_id: str, snapshot: ControlRecoverySnapshot, emergency_state: EmergencyState | str, live_authorization_valid: bool, reason: str, failures: tuple[str, ...], actor: str) -> None:
        with self.connection_factory() as tx:
            repo = ControlRecoveryAuditRepository(tx)
            repo.append(
                new_recovery_audit_record(
                    event_id=event_id,
                    event_type=event_type,
                    phase=snapshot.recovery.phase.value,
                    control_state=snapshot.control_state.value,
                    emergency_state=EmergencyState(emergency_state).value,
                    live_authorization_valid=live_authorization_valid,
                    failures=failures,
                    reason=reason,
                    actor=actor,
                )
            )

    def observe(self, readiness: Mapping[str, bool], *, emergency_state: EmergencyState | str, live_authorization_valid: bool, actor: str = "runtime"):
        status = self.integration.observe(
            readiness,
            control_state=self.integration.controller.machine.state,
            emergency_state=emergency_state,
            live_authorization_valid=live_authorization_valid,
        )
        snap = self.integration.snapshot()
        self._persist(
            event_type="RECOVERY_OBSERVE",
            event_id=self.event_id_factory(),
            snapshot=snap,
            emergency_state=emergency_state,
            live_authorization_valid=live_authorization_valid,
            reason=status.reason,
            failures=status.failures,
            actor=actor,
        )
        return status

    def explicit_resume(self, readiness: Mapping[str, bool], *, emergency_state: EmergencyState | str, live_authorization_valid: bool, actor: str = "operator"):
        status = self.integration.explicit_resume(
            readiness,
            emergency_state=emergency_state,
            live_authorization_valid=live_authorization_valid,
        )
        snap = self.integration.snapshot()
        self._persist(
            event_type="RECOVERY_RESUME",
            event_id=self.event_id_factory(),
            snapshot=snap,
            emergency_state=emergency_state,
            live_authorization_valid=live_authorization_valid,
            reason=status.reason,
            failures=status.failures,
            actor=actor,
        )
        return status


__all__ = ["PersistentControlRecoveryIntegration", "PersistentRecoveryEvent"]
