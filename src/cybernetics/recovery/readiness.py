from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReadinessInputs:
    persistence_ready: bool
    recovery_clear: bool
    orders_reconciled: bool
    positions_reconciled: bool
    market_data_ready: bool
    scanner_health_ready: bool
    emergency_stop_active: bool
    live_authorization_valid: bool


@dataclass(frozen=True)
class ReadinessDecision:
    ready_for_engine: bool
    ready_for_new_trades: bool
    reasons: tuple[str, ...]


def evaluate_readiness(inputs: ReadinessInputs) -> ReadinessDecision:
    reasons: list[str] = []

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

    engine_ready = not reasons
    new_trades_ready = (
        engine_ready
        and not inputs.emergency_stop_active
        and inputs.live_authorization_valid
    )

    if inputs.emergency_stop_active:
        reasons.append("emergency_stop_active")
    if not inputs.live_authorization_valid:
        reasons.append("live_authorization_invalid")

    return ReadinessDecision(
        ready_for_engine=engine_ready,
        ready_for_new_trades=new_trades_ready,
        reasons=tuple(reasons),
    )
