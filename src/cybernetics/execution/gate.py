from __future__ import annotations
from dataclasses import dataclass
from enum import Enum

class ExecutionDecision(str, Enum):
    ALLOW="ALLOW"
    BLOCK="BLOCK"

@dataclass(frozen=True)
class ExecutionInputs:
    engine_ready: bool
    new_trades_allowed: bool
    emergency_active: bool
    live_authorization_valid: bool
    reconciliation_ready: bool
    risk_approved: bool
    pretrade_approved: bool
    broker_available: bool
    positive_quantity: bool
    positive_price: bool

@dataclass(frozen=True)
class ExecutionResult:
    decision: ExecutionDecision
    reasons: tuple[str,...]

def evaluate_entry(inputs: ExecutionInputs)->ExecutionResult:
    reasons=[]
    if not inputs.engine_ready: reasons.append("engine_not_ready")
    if not inputs.new_trades_allowed: reasons.append("new_trades_not_allowed")
    if inputs.emergency_active: reasons.append("emergency_stop_active")
    if not inputs.live_authorization_valid: reasons.append("live_authorization_invalid")
    if not inputs.reconciliation_ready: reasons.append("reconciliation_not_ready")
    if not inputs.risk_approved: reasons.append("risk_not_approved")
    if not inputs.pretrade_approved: reasons.append("pretrade_not_approved")
    if not inputs.broker_available: reasons.append("broker_unavailable")
    if not inputs.positive_quantity: reasons.append("quantity_invalid")
    if not inputs.positive_price: reasons.append("price_invalid")
    return ExecutionResult(
        ExecutionDecision.ALLOW if not reasons else ExecutionDecision.BLOCK,
        tuple(reasons)
    )
