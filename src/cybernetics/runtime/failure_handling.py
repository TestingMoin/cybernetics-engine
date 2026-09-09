from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

from .state import ControlState, EmergencyState


@dataclass(frozen=True)
class DependencyFailure:
    name: str
    reason: str = "unhealthy"


@dataclass(frozen=True)
class SafeStateAction:
    requested: bool
    action: str
    failures: tuple[DependencyFailure, ...]
    reason: str


class RuntimeDependencyFailureHandler:
    """Turn runtime dependency loss into an explicit safe control state.

    Dependency failure does not automatically assert the emergency latch. It
    moves an otherwise RUNNING runtime to STOP_NEW_TRADES so new entries stop
    while the independent exit/emergency mechanisms retain ownership of open
    positions and flattening.
    """

    CRITICAL_DEPENDENCIES = (
        "persistence",
        "recovery",
        "market_data",
        "scanners",
        "watchdog",
        "broker",
    )

    def __init__(self, *, set_control_state: Callable[[ControlState], None] | None = None) -> None:
        self._set_control_state = set_control_state
        self._last_failures: tuple[DependencyFailure, ...] = ()
        self._last_action = SafeStateAction(False, "NONE", (), "dependencies_healthy")

    @property
    def last_action(self) -> SafeStateAction:
        return self._last_action

    @property
    def last_failures(self) -> tuple[DependencyFailure, ...]:
        return self._last_failures

    def evaluate(
        self,
        readiness: dict[str, bool],
        *,
        control_state: ControlState | str,
        emergency_state: EmergencyState | str,
    ) -> SafeStateAction:
        control = ControlState(control_state)
        emergency = EmergencyState(emergency_state)
        failures = tuple(
            DependencyFailure(name=name)
            for name in self.CRITICAL_DEPENDENCIES
            if not bool(readiness.get(name, False))
        )
        self._last_failures = failures

        if not failures:
            action = SafeStateAction(False, "NONE", (), "dependencies_healthy")
        elif emergency is EmergencyState.ACTIVE:
            action = SafeStateAction(False, "NONE", failures, "emergency_state_already_active")
        elif control is ControlState.RUNNING:
            if self._set_control_state is not None:
                self._set_control_state(ControlState.STOP_NEW_TRADES)
            action = SafeStateAction(True, "STOP_NEW_TRADES", failures, "critical_dependency_failure")
        else:
            action = SafeStateAction(False, "NONE", failures, "already_non_trading_control_state")

        self._last_action = action
        return action
