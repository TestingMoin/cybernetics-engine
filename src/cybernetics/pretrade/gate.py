from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class GateDecision(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class PreTradeContext:
    """
    Final deterministic gate inputs immediately before execution.

    This contract intentionally contains evidence/results from upstream layers,
    rather than calling those layers itself. The gate is therefore easy to
    audit and replay.
    """
    engine_running: bool
    emergency_stop: bool
    live_authorized: bool
    reconciliation_ok: bool
    market_data_ready: bool
    scanner_healthy: bool
    signal_qualified: bool
    strategy_decision_valid: bool
    position_state_valid: bool

    risk_approved: bool
    sizing_approved: bool
    quantity: int = 0
    lot_size: int = 1

    execution_mode: str = "paper"
    action: str = "NO_ACTION"

    # Optional system controls
    broker_available: bool = True
    max_daily_loss_reached: bool = False
    max_exposure_reached: bool = False
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class GateResult:
    decision: GateDecision
    reason: str
    failed_checks: tuple[str, ...] = ()
    quantity: int = 0


class ComprehensivePreTradeGate:
    """
    Single deterministic final barrier before order creation.

    It never creates broker payloads and never submits/cancels orders.
    """

    def evaluate(self, ctx: PreTradeContext) -> GateResult:
        failed: list[str] = []

        action = ctx.action.upper()

        # Universal safety/system checks.
        if not ctx.engine_running:
            failed.append("engine_not_running")
        if ctx.emergency_stop:
            failed.append("emergency_stop_active")
        if not ctx.reconciliation_ok:
            failed.append("reconciliation_not_ok")
        if not ctx.market_data_ready:
            failed.append("market_data_not_ready")
        if not ctx.scanner_healthy:
            failed.append("scanner_unhealthy")
        if not ctx.broker_available:
            failed.append("broker_unavailable")

        # A strategy decision has to be meaningful before risk is considered.
        if not ctx.signal_qualified:
            failed.append("signal_not_qualified")
        if not ctx.strategy_decision_valid:
            failed.append("strategy_decision_invalid")
        if not ctx.position_state_valid:
            failed.append("position_state_invalid")

        # The final gate requires both upstream risk and sizing approval for
        # executable entries. Exits may use a safety path but still require
        # system/reconciliation/data controls.
        if action in {"ENTER_LONG", "ENTER_SHORT"}:
            if not ctx.risk_approved:
                failed.append("risk_not_approved")
            if not ctx.sizing_approved:
                failed.append("sizing_not_approved")
            if ctx.max_daily_loss_reached:
                failed.append("daily_loss_limit_reached")
            if ctx.max_exposure_reached:
                failed.append("max_exposure_reached")
            if ctx.quantity <= 0:
                failed.append("quantity_invalid")
            elif ctx.quantity % max(ctx.lot_size, 1) != 0:
                failed.append("quantity_not_lot_aligned")

            if ctx.execution_mode == "live" and not ctx.live_authorized:
                failed.append("live_authorization_missing")

        elif action in {"EXIT_LONG", "EXIT_SHORT", "EXIT"}:
            # Exits remain permitted through the safety path even if entry risk
            # restrictions have been reached.
            pass
        else:
            failed.append("non_executable_action")

        if failed:
            return GateResult(
                GateDecision.REJECTED,
                failed[0],
                tuple(failed),
                quantity=ctx.quantity,
            )

        return GateResult(
            GateDecision.APPROVED,
            "pretrade_checks_passed",
            (),
            quantity=ctx.quantity,
        )
