from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from cybernetics.runtime.control import (
    ControlAction,
    ControlState as MachineControlState,
    GuardedController,
    TransitionPolicy,
)
from cybernetics.runtime.recovery_resume import (
    RecoveryPhase,
    RecoveryStatus,
    SafeStateRecoveryCoordinator,
)
from cybernetics.runtime.state import ControlState, EmergencyState


@dataclass(frozen=True)
class ControlRecoverySnapshot:
    control_state: MachineControlState
    recovery: RecoveryStatus


class ControlRecoveryIntegration:
    """Single control/recovery boundary for failure-safe resume.

    Dependency failures are handled by the runtime failure path, which should
    place the process in STOP_NEW_TRADES. This adapter owns the *resume* side:
    the recovery coordinator cannot move the control state directly; it must
    use the authoritative guarded control state machine with its live-approval
    policy. Thus recovery readiness never bypasses the control gateway/state
    machine.
    """

    def __init__(self, controller: GuardedController) -> None:
        self.controller = controller
        self.recovery = SafeStateRecoveryCoordinator(
            set_control_state=self._resume_control_state,
        )

    def _resume_control_state(self, state: ControlState) -> None:
        if state is not ControlState.RUNNING:
            raise ValueError("only_running_resume_supported")
        self.controller.apply(
            ControlAction.RESUME_NEW_TRADES,
            TransitionPolicy(live_authorization_valid=True, recovery_clear=True),
        )

    def observe(
        self,
        readiness: Mapping[str, bool],
        *,
        control_state: MachineControlState | ControlState | str,
        emergency_state: EmergencyState | str,
        live_authorization_valid: bool,
    ) -> RecoveryStatus:
        # The recovery coordinator and state machine must agree on control
        # state. Invalid/mismatched values fail closed rather than coercing an
        # unsafe state transition.
        machine_state = MachineControlState(control_state)
        runtime_control = ControlState(
            ControlState.STOP_NEW_TRADES.value
            if machine_state is MachineControlState.STOP_NEW_TRADES
            else ControlState.RUNNING.value
            if machine_state is MachineControlState.RUNNING
            else ControlState.EMERGENCY_STOP.value
        )
        return self.recovery.observe(
            readiness,
            control_state=runtime_control,
            emergency_state=emergency_state,
            live_authorization_valid=live_authorization_valid,
        )

    def explicit_resume(
        self,
        readiness: Mapping[str, bool],
        *,
        emergency_state: EmergencyState | str,
        live_authorization_valid: bool,
    ) -> RecoveryStatus:
        if self.controller.machine.state is not MachineControlState.STOP_NEW_TRADES:
            raise RuntimeError("resume_requires_stop_new_trades")
        return self.recovery.resume(
            control_state=ControlState.STOP_NEW_TRADES,
            emergency_state=emergency_state,
            live_authorization_valid=live_authorization_valid,
            readiness=readiness,
        )

    def snapshot(self) -> ControlRecoverySnapshot:
        return ControlRecoverySnapshot(
            control_state=self.controller.machine.state,
            recovery=self.recovery.status,
        )


__all__ = ["ControlRecoveryIntegration", "ControlRecoverySnapshot"]
