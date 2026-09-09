from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from .lifecycle import SignalLifecycleManager, SignalLifecycleState

@dataclass(frozen=True)
class QualificationResult:
    signal_id: str
    qualified: bool
    reason: str

class SignalQualifier:
    """
    Final deterministic validity check before a signal is handed to strategy
    evaluation. It checks lifecycle, optional scanner/data-quality gates and
    minimum evidence strength. It still never creates an order.
    """
    def __init__(self, lifecycle: SignalLifecycleManager,
                 minimum_strength: float=0.0):
        if not 0 <= minimum_strength <= 1:
            raise ValueError("minimum_strength_out_of_range")
        self.lifecycle=lifecycle
        self.minimum_strength=minimum_strength

    def qualify(self, signal_id: str, *,
                strength: float,
                scanner_healthy: bool=True,
                data_ready: bool=True)->QualificationResult:
        if not 0 <= strength <= 1:
            raise ValueError("signal_strength_out_of_range")
        current=self.lifecycle.evaluate(signal_id)
        if current.state not in {SignalLifecycleState.OBSERVED,SignalLifecycleState.ACTIVE}:
            return QualificationResult(signal_id,False,f"lifecycle:{current.state.value}")
        if not scanner_healthy:
            return QualificationResult(signal_id,False,"scanner_unhealthy")
        if not data_ready:
            return QualificationResult(signal_id,False,"market_data_not_ready")
        if strength < self.minimum_strength:
            return QualificationResult(signal_id,False,"strength_below_threshold")
        return QualificationResult(signal_id,True,"qualified")
