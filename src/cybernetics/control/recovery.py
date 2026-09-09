from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional

class RecoveryStage(str, Enum):
    LOAD_STATE="LOAD_STATE"
    BROKER_CHECK="BROKER_CHECK"
    RECONCILE="RECONCILE"
    RESTORE_DATA="RESTORE_DATA"
    RESTORE_STRATEGIES="RESTORE_STRATEGIES"
    SAFE_HOLD="SAFE_HOLD"
    READY="READY"
    FAILED="FAILED"

@dataclass(frozen=True)
class RecoveryResult:
    success: bool
    stage: RecoveryStage
    reason: str
    new_trades_allowed: bool

class RecoveryOrchestrator:
    """Startup/crash recovery coordinator. It defaults to safe-hold."""
    def recover(self, *, load_state:Callable[[],bool],
                broker_check:Callable[[],bool],
                reconcile:Callable[[],bool],
                restore_data:Callable[[],bool],
                restore_strategies:Callable[[],bool]) -> RecoveryResult:
        checks=[
            (RecoveryStage.LOAD_STATE,load_state),
            (RecoveryStage.BROKER_CHECK,broker_check),
            (RecoveryStage.RECONCILE,reconcile),
            (RecoveryStage.RESTORE_DATA,restore_data),
            (RecoveryStage.RESTORE_STRATEGIES,restore_strategies),
        ]
        for stage,fn in checks:
            try:
                ok=bool(fn())
            except Exception as exc:
                return RecoveryResult(False,RecoveryStage.FAILED,f"{stage.value}:{exc}",False)
            if not ok:
                return RecoveryResult(False,RecoveryStage.FAILED,f"{stage.value}:check_failed",False)
        return RecoveryResult(True,RecoveryStage.READY,"recovery_checks_passed",True)
