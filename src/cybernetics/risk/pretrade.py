from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class PreTradeContext:
    engine_enabled: bool
    live_authorized: bool
    kill_switch_active: bool
    emergency_stop: bool
    data_quality_ok: bool
    strategy_approved: bool
    risk_approved: bool

@dataclass(frozen=True)
class PreTradeDecision:
    allowed: bool
    reasons: tuple[str,...]

class PreTradeGate:
    def evaluate(self, c: PreTradeContext) -> PreTradeDecision:
        reasons=[]
        if not c.engine_enabled: reasons.append("engine_disabled")
        if not c.live_authorized: reasons.append("live_not_authorized")
        if c.kill_switch_active: reasons.append("kill_switch_active")
        if c.emergency_stop: reasons.append("emergency_stop")
        if not c.data_quality_ok: reasons.append("data_quality_failed")
        if not c.strategy_approved: reasons.append("strategy_not_approved")
        if not c.risk_approved: reasons.append("risk_not_approved")
        return PreTradeDecision(not reasons, tuple(reasons))
