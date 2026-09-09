from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class RecoveryAction:
    action: str
    reason: str

class ReconciliationManager:
    """Turns reconciliation results into safe control-plane actions."""
    def decide(self, report) -> RecoveryAction:
        if report.matched:
            return RecoveryAction("RESUME","internal_and_broker_state_match")
        return RecoveryAction("BLOCK_NEW_TRADES","reconciliation_mismatch_requires_resolution")
