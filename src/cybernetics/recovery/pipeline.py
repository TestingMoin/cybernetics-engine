from __future__ import annotations
from dataclasses import dataclass
from .gap_detector import DataGap, GapDetector
from .coordinator import RecoveryCoordinator, RecoveryResult, RecoveryState

@dataclass(frozen=True)
class GapRecoveryReport:
    gaps: tuple[DataGap,...]
    results: tuple[RecoveryResult,...]
    ready: bool

class GapRecoveryPipeline:
    """
    Detects and repairs gaps. Downstream consumers should treat `ready=False`
    as a hard data-integrity block for the affected instrument.
    """
    def __init__(self, detector:GapDetector, coordinator:RecoveryCoordinator):
        self.detector=detector
        self.coordinator=coordinator

    def run(self, security_id, timestamps, expected_interval)->GapRecoveryReport:
        gaps=self.detector.detect(security_id,timestamps,expected_interval)
        if not gaps:
            return GapRecoveryReport(tuple(),tuple(),True)

        results=tuple(self.coordinator.recover(g) for g in gaps)
        ready=all(r.state==RecoveryState.VERIFIED for r in results)
        return GapRecoveryReport(tuple(gaps),results,ready)
