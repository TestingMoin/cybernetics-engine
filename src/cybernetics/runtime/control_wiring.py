from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .state import ControlState, EmergencyState


class ControlRuntimeWiringError(ValueError):
    """Raised when the control runtime boundary cannot provide safe state."""


@dataclass(frozen=True)
class ControlRuntimeSnapshot:
    control_state: ControlState
    emergency_state: EmergencyState


class ControlRuntimeWiring:
    """Read-only adapter from durable/runtime control state to readiness inputs.

    The wiring layer does not transition state and does not clear an emergency
    latch.  Mutations remain owned by the control gateway/emergency subsystem.
    """

    def __init__(
        self,
        *,
        control_state: ControlState | str | Callable[[], ControlState | str],
        emergency_state: EmergencyState | str | Callable[[], EmergencyState | str],
    ) -> None:
        self._control_state = control_state
        self._emergency_state = emergency_state

    @staticmethod
    def _resolve(value):
        return value() if callable(value) else value

    def snapshot(self) -> ControlRuntimeSnapshot:
        try:
            control = ControlState(self._resolve(self._control_state))
            emergency = EmergencyState(self._resolve(self._emergency_state))
        except Exception as exc:
            raise ControlRuntimeWiringError("control_state_probe_error") from exc
        if emergency is EmergencyState.ACTIVE and control is ControlState.RUNNING:
            # Emergency is independently authoritative; do not silently rewrite
            # control state, but expose the unsafe combination to readiness.
            return ControlRuntimeSnapshot(control, emergency)
        return ControlRuntimeSnapshot(control, emergency)

    def control_state(self) -> ControlState:
        return self.snapshot().control_state

    def emergency_state(self) -> EmergencyState:
        return self.snapshot().emergency_state

    def safe_for_new_trades(self) -> bool:
        snap = self.snapshot()
        return (
            snap.control_state is ControlState.RUNNING
            and snap.emergency_state is EmergencyState.CLEAR
        )
