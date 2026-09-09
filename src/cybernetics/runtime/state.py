from __future__ import annotations
from dataclasses import dataclass
from enum import Enum


class EngineMode(str, Enum):
    STOPPED = "STOPPED"
    RUNNING = "RUNNING"


class EmergencyState(str, Enum):
    CLEAR = "CLEAR"
    ACTIVE = "ACTIVE"


class ControlState(str, Enum):
    RUNNING = "RUNNING"
    STOP_NEW_TRADES = "STOP_NEW_TRADES"
    EMERGENCY_STOP = "EMERGENCY_STOP"


@dataclass(frozen=True)
class RuntimeInputs:
    engine_mode: EngineMode
    control_state: ControlState
    persistence_ready: bool
    recovery_clear: bool
    orders_reconciled: bool
    positions_reconciled: bool
    market_data_ready: bool
    scanner_health_ready: bool
    watchdog_healthy: bool
    live_authorization_valid: bool
    broker_available: bool
    emergency_state: EmergencyState = EmergencyState.CLEAR


@dataclass(frozen=True)
class RuntimeReadiness:
    engine_ready: bool
    new_trades_allowed: bool
    reasons: tuple[str, ...]


def evaluate_runtime(inputs: RuntimeInputs) -> RuntimeReadiness:
    reasons: list[str] = []
    engine_mode = inputs.engine_mode if isinstance(inputs.engine_mode, EngineMode) else EngineMode(inputs.engine_mode)
    control_state = inputs.control_state if isinstance(inputs.control_state, ControlState) else ControlState(inputs.control_state)
    emergency_state = inputs.emergency_state if isinstance(inputs.emergency_state, EmergencyState) else EmergencyState(inputs.emergency_state)

    if engine_mode is not EngineMode.RUNNING:
        reasons.append("engine_not_running")
    if control_state is ControlState.EMERGENCY_STOP or emergency_state is EmergencyState.ACTIVE:
        reasons.append("emergency_stop_active")
    if control_state is ControlState.STOP_NEW_TRADES:
        reasons.append("stop_new_trades")
    if not inputs.persistence_ready:
        reasons.append("persistence_not_ready")
    if not inputs.recovery_clear:
        reasons.append("recovery_not_clear")
    if not inputs.orders_reconciled:
        reasons.append("orders_not_reconciled")
    if not inputs.positions_reconciled:
        reasons.append("positions_not_reconciled")
    if not inputs.market_data_ready:
        reasons.append("market_data_not_ready")
    if not inputs.scanner_health_ready:
        reasons.append("scanner_health_not_ready")
    if not inputs.watchdog_healthy:
        reasons.append("watchdog_not_healthy")
    if not inputs.broker_available:
        reasons.append("broker_unavailable")

    engine_ready = not any(
        r in reasons for r in (
            "engine_not_running",
            "persistence_not_ready",
            "recovery_not_clear",
            "orders_not_reconciled",
            "positions_not_reconciled",
            "market_data_not_ready",
            "scanner_health_not_ready",
            "watchdog_not_healthy",
            "broker_unavailable",
        )
    )

    new_trades_allowed = (
        engine_ready
        and control_state is ControlState.RUNNING
        and emergency_state is EmergencyState.CLEAR
        and inputs.live_authorization_valid
    )

    if not inputs.live_authorization_valid:
        reasons.append("live_authorization_invalid")

    return RuntimeReadiness(
        engine_ready=engine_ready,
        new_trades_allowed=new_trades_allowed,
        reasons=tuple(reasons),
    )
