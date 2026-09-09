from __future__ import annotations
from dataclasses import dataclass
from typing import Any

from cybernetics.signals.lifecycle import SignalLifecycleManager, SignalLifecycleState
from cybernetics.signals.qualification import SignalQualifier
from .engine import StrategyEngine
from .models import StrategyContext, StrategyDecision

@dataclass(frozen=True)
class StrategyEvaluationResult:
    accepted: bool
    reason: str
    decision: StrategyDecision | None = None

class QualifiedSignalStrategyBridge:
    """
    Converts a signal-record payload into StrategyContext only after lifecycle
    and qualification checks. It prevents stale/unqualified signals reaching
    strategy evaluation.
    """
    def __init__(self, lifecycle: SignalLifecycleManager,
                 qualifier: SignalQualifier, engine: StrategyEngine):
        self.lifecycle = lifecycle
        self.qualifier = qualifier
        self.engine = engine

    def evaluate(self, strategy_id: str, *,
                 signal_id: str, scanner_id: str, underlying_key: str,
                 timeframe: str, timestamp, direction: str | None,
                 strength: float, evidence: dict[str, Any] | None = None,
                 scanner_healthy: bool = True,
                 data_ready: bool = True) -> StrategyEvaluationResult:
        q=self.qualifier.qualify(
            signal_id,
            strength=strength,
            scanner_healthy=scanner_healthy,
            data_ready=data_ready,
        )
        if not q.qualified:
            return StrategyEvaluationResult(False,q.reason,None)

        ctx=StrategyContext(
            signal_id=signal_id,
            scanner_id=scanner_id,
            underlying_key=underlying_key,
            timeframe=timeframe,
            timestamp=timestamp,
            direction=direction,
            strength=strength,
            evidence=evidence or {},
        )
        try:
            decision=self.engine.evaluate(strategy_id,ctx)
        except Exception as exc:
            return StrategyEvaluationResult(False,f"strategy_error:{type(exc).__name__}:{exc}",None)
        return StrategyEvaluationResult(True,"strategy_decision_created",decision)
