from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Mapping

from .state import ControlState, EmergencyState
from .failure_handling import RuntimeDependencyFailureHandler


class RecoveryPhase(str, Enum):
    NORMAL = "NORMAL"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"
    RECOVERY_READY = "RECOVERY_READY"
    RESUMED = "RESUMED"


@dataclass(frozen=True)
class RecoveryStatus:
    phase: RecoveryPhase
    failures: tuple[str, ...]
    resume_allowed: bool
    reason: str


class SafeStateRecoveryCoordinator:
    """Explicit recovery/resume gate after a runtime dependency failure.

    Dependency health recovery never auto-resumes trading. The coordinator
    first records recovery-required state, then exposes RECOVERY_READY only
    after all critical dependencies are healthy. A separate explicit resume
    request is required, and it additionally requires live authorization,
    STOP_NEW_TRADES control state, and a clear emergency state.
    """

    def __init__(
        self,
        *,
        set_control_state: Callable[[ControlState], None] | None = None,
    ) -> None:
        self._set_control_state = set_control_state
        self._phase = RecoveryPhase.NORMAL
        self._failures: tuple[str, ...] = ()
        self._reason = "healthy"

    @property
    def status(self) -> RecoveryStatus:
        return RecoveryStatus(
            phase=self._phase,
            failures=self._failures,
            resume_allowed=self._phase is RecoveryPhase.RECOVERY_READY,
            reason=self._reason,
        )

    def observe(
        self,
        readiness: Mapping[str, bool],
        *,
        control_state: ControlState | str,
        emergency_state: EmergencyState | str,
        live_authorization_valid: bool,
    ) -> RecoveryStatus:
        control = ControlState(control_state)
        emergency = EmergencyState(emergency_state)
        failures = tuple(
            name
            for name in RuntimeDependencyFailureHandler.CRITICAL_DEPENDENCIES
            if not bool(readiness.get(name, False))
        )
        self._failures = failures

        if failures:
            self._phase = RecoveryPhase.RECOVERY_REQUIRED
            self._reason = "critical_dependencies_unhealthy"
            return self.status

        # A healthy runtime does not imply authorization to resume. Recovery
        # must be explicitly completed after the prior safe-state condition.
        if self._phase is RecoveryPhase.RECOVERY_REQUIRED:
            if emergency is EmergencyState.ACTIVE:
                self._phase = RecoveryPhase.RECOVERY_REQUIRED
                self._reason = "emergency_stop_active"
            elif control is not ControlState.STOP_NEW_TRADES:
                self._phase = RecoveryPhase.RECOVERY_REQUIRED
                self._reason = "safe_control_state_required"
            elif not live_authorization_valid:
                self._phase = RecoveryPhase.RECOVERY_REQUIRED
                self._reason = "live_authorization_required_for_resume"
            else:
                self._phase = RecoveryPhase.RECOVERY_READY
                self._reason = "recovery_checks_passed_explicit_resume_required"
            return self.status

        if self._phase is RecoveryPhase.RECOVERY_READY:
            # Keep explicit-resume state until resume() is called.
            self._reason = "explicit_resume_required"
            return self.status

        if self._phase is RecoveryPhase.RESUMED:
            self._reason = "resumed"
            return self.status

        self._phase = RecoveryPhase.NORMAL
        self._reason = "healthy"
        return self.status

    def resume(
        self,
        *,
        control_state: ControlState | str,
        emergency_state: EmergencyState | str,
        live_authorization_valid: bool,
        readiness: Mapping[str, bool],
    ) -> RecoveryStatus:
        """Explicitly request resume; never invoked implicitly by observe()."""
        control = ControlState(control_state)
        emergency = EmergencyState(emergency_state)
        failures = tuple(
            name
            for name in RuntimeDependencyFailureHandler.CRITICAL_DEPENDENCIES
            if not bool(readiness.get(name, False))
        )
        if self._phase is not RecoveryPhase.RECOVERY_READY:
            raise RuntimeError("recovery_not_ready_for_resume")
        if failures:
            self._phase = RecoveryPhase.RECOVERY_REQUIRED
            self._failures = failures
            self._reason = "dependencies_failed_before_resume"
            raise RuntimeError("dependencies_not_healthy")
        if emergency is EmergencyState.ACTIVE:
            self._reason = "emergency_stop_active"
            raise RuntimeError("emergency_stop_active")
        if control is not ControlState.STOP_NEW_TRADES:
            self._reason = "stop_new_trades_control_required"
            raise RuntimeError("resume_requires_stop_new_trades")
        if not live_authorization_valid:
            self._reason = "live_authorization_required_for_resume"
            raise RuntimeError("live_authorization_required")

        if self._set_control_state is None:
            self._reason = "resume_callback_required"
            raise RuntimeError("resume_callback_required")
        self._set_control_state(ControlState.RUNNING)
        self._phase = RecoveryPhase.RESUMED
        self._reason = "explicit_resume_approved"
        return self.status


__all__ = ["RecoveryPhase", "RecoveryStatus", "SafeStateRecoveryCoordinator"]
