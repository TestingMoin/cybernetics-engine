from __future__ import annotations

from dataclasses import dataclass

from .dependencies import RuntimeDependencyBundle
from .state import (
    ControlState,
    EmergencyState,
    EngineMode,
    RuntimeInputs,
    RuntimeReadiness,
    evaluate_runtime,
)


@dataclass(frozen=True)
class RuntimeCoreState:
    """Non-dependency runtime state supplied by the control/composition root."""

    engine_mode: EngineMode = EngineMode.STOPPED
    control_state: ControlState = ControlState.STOP_NEW_TRADES
    emergency_state: EmergencyState = EmergencyState.CLEAR
    orders_reconciled: bool = False
    positions_reconciled: bool = False
    live_authorization_valid: bool = False


@dataclass(frozen=True)
class UnifiedRuntimeReadiness:
    """Deterministic, side-effect-free readiness result across all runtime gates."""

    inputs: RuntimeInputs
    readiness: RuntimeReadiness
    dependency_readiness: dict[str, bool]


class FullRuntimeReadinessEvaluator:
    """Combines the canonical dependency bundle with core runtime state.

    The evaluator only invokes injected readiness probes. It never starts services,
    performs broker I/O, mutates persistence, or changes control state.
    """

    def __init__(self, dependencies: RuntimeDependencyBundle, core: RuntimeCoreState):
        self._dependencies = dependencies
        self._core = core

    def evaluate(self) -> UnifiedRuntimeReadiness:
        dependency = self._dependencies.readiness()
        inputs = RuntimeInputs(
            engine_mode=self._core.engine_mode,
            control_state=self._core.control_state,
            emergency_state=self._core.emergency_state,
            persistence_ready=dependency["persistence"],
            recovery_clear=dependency["recovery"],
            orders_reconciled=self._core.orders_reconciled,
            positions_reconciled=self._core.positions_reconciled,
            market_data_ready=dependency["market_data"],
            scanner_health_ready=dependency["scanners"],
            watchdog_healthy=dependency["watchdog"],
            broker_available=dependency["broker"],
            live_authorization_valid=self._core.live_authorization_valid,
        )
        return UnifiedRuntimeReadiness(inputs, evaluate_runtime(inputs), dependency)


def evaluate_full_runtime_readiness(
    dependencies: RuntimeDependencyBundle, core: RuntimeCoreState
) -> UnifiedRuntimeReadiness:
    return FullRuntimeReadinessEvaluator(dependencies, core).evaluate()
