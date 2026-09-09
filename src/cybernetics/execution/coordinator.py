from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Any

class ExecutionBlock(str, Enum):
    NONE="NONE"
    ENGINE_STOPPED="ENGINE_STOPPED"
    LIVE_NOT_AUTHORIZED="LIVE_NOT_AUTHORIZED"
    EMERGENCY_STOP="EMERGENCY_STOP"
    RISK_REJECTED="RISK_REJECTED"
    PRETRADE_REJECTED="PRETRADE_REJECTED"
    RECONCILIATION_FAILED="RECONCILIATION_FAILED"
    BROKER_UNAVAILABLE="BROKER_UNAVAILABLE"

@dataclass(frozen=True)
class ExecutionContext:
    engine_running: bool
    live_authorized: bool
    emergency_stop: bool
    risk_approved: bool
    pretrade_approved: bool
    reconciliation_ok: bool
    broker_available: bool

@dataclass(frozen=True)
class ExecutionDecision:
    allowed: bool
    block: ExecutionBlock
    reason: str

class ExecutionCoordinator:
    def authorize(self, ctx: ExecutionContext) -> ExecutionDecision:
        checks = (
            (ctx.engine_running, ExecutionBlock.ENGINE_STOPPED, "engine_not_running"),
            (ctx.emergency_stop is False, ExecutionBlock.EMERGENCY_STOP, "emergency_stop_active"),
            (ctx.live_authorized, ExecutionBlock.LIVE_NOT_AUTHORIZED, "live_not_authorized"),
            (ctx.risk_approved, ExecutionBlock.RISK_REJECTED, "risk_rejected"),
            (ctx.pretrade_approved, ExecutionBlock.PRETRADE_REJECTED, "pretrade_rejected"),
            (ctx.reconciliation_ok, ExecutionBlock.RECONCILIATION_FAILED, "reconciliation_not_ok"),
            (ctx.broker_available, ExecutionBlock.BROKER_UNAVAILABLE, "broker_unavailable"),
        )
        for ok, block, reason in checks:
            if not ok:
                return ExecutionDecision(False, block, reason)
        return ExecutionDecision(True, ExecutionBlock.NONE, "execution_authorized")
