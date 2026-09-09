from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .state import (
    ControlState,
    EmergencyState,
    EngineMode,
    RuntimeInputs,
    RuntimeReadiness,
    evaluate_runtime,
)


class RuntimeSignals(Protocol):
    def engine_mode(self): ...
    def control_state(self): ...
    def persistence_ready(self): ...
    def recovery_clear(self): ...
    def orders_reconciled(self): ...
    def positions_reconciled(self): ...
    def market_data_ready(self): ...
    def scanner_health_ready(self): ...
    def watchdog_healthy(self): ...
    def live_authorization_valid(self): ...
    def broker_available(self): ...
    def emergency_state(self): ...


@dataclass(frozen=True)
class RuntimeSnapshot:
    inputs: RuntimeInputs
    readiness: RuntimeReadiness


class RuntimeStateComposer:
    """Read-only composition layer for canonical runtime state."""

    def __init__(self, signals: RuntimeSignals):
        self.signals = signals

    def snapshot(self) -> RuntimeSnapshot:
        inputs = RuntimeInputs(
            engine_mode=self.signals.engine_mode(),
            control_state=self.signals.control_state(),
            persistence_ready=self.signals.persistence_ready(),
            recovery_clear=self.signals.recovery_clear(),
            orders_reconciled=self.signals.orders_reconciled(),
            positions_reconciled=self.signals.positions_reconciled(),
            market_data_ready=self.signals.market_data_ready(),
            scanner_health_ready=self.signals.scanner_health_ready(),
            watchdog_healthy=self.signals.watchdog_healthy(),
            live_authorization_valid=self.signals.live_authorization_valid(),
            broker_available=self.signals.broker_available(),
            emergency_state=(self.signals.emergency_state() if hasattr(self.signals, "emergency_state") else EmergencyState.CLEAR),
        )
        return RuntimeSnapshot(inputs, evaluate_runtime(inputs))
