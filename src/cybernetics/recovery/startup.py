from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Protocol


class StartupStage(str, Enum):
    CREATED = "CREATED"
    PERSISTENCE_VALIDATED = "PERSISTENCE_VALIDATED"
    RECOVERY_DISCOVERED = "RECOVERY_DISCOVERED"
    BROKER_RECONCILED = "BROKER_RECONCILED"
    POSITIONS_RECONCILED = "POSITIONS_RECONCILED"
    READINESS_EVALUATED = "READINESS_EVALUATED"
    READY = "READY"
    BLOCKED = "BLOCKED"


class Readiness(str, Enum):
    READY = "READY"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class StartupFinding:
    code: str
    detail: str
    blocking: bool = True


@dataclass(frozen=True)
class StartupReport:
    stage: StartupStage
    readiness: Readiness
    findings: tuple[StartupFinding, ...]


class StartupRecoveryDependencies(Protocol):
    def validate_persistence(self) -> bool: ...
    def find_unresolved_recovery_cases(self) -> Iterable[str]: ...
    def reconcile_orders(self) -> bool: ...
    def reconcile_positions(self) -> bool: ...


class StartupRecoveryOrchestrator:
    """
    Conservative restart orchestrator.

    The engine cannot become READY merely because the process started. It must
    first validate persistence, discover unresolved recovery state, reconcile
    broker/internal orders and positions, and then evaluate readiness.

    This component never enables live trading and never submits/cancels/replaces
    broker orders.
    """

    def __init__(self, deps: StartupRecoveryDependencies):
        self.deps = deps

    def run(self) -> StartupReport:
        findings: list[StartupFinding] = []

        if not self.deps.validate_persistence():
            findings.append(
                StartupFinding(
                    "PERSISTENCE_NOT_READY",
                    "required persistence infrastructure is unavailable",
                )
            )
            return StartupReport(
                StartupStage.BLOCKED, Readiness.BLOCKED, tuple(findings)
            )

        unresolved = tuple(self.deps.find_unresolved_recovery_cases())
        if unresolved:
            findings.append(
                StartupFinding(
                    "UNRESOLVED_RECOVERY_CASES",
                    f"{len(unresolved)} recovery case(s) remain unresolved",
                )
            )
            return StartupReport(
                StartupStage.BLOCKED, Readiness.BLOCKED, tuple(findings)
            )

        if not self.deps.reconcile_orders():
            findings.append(
                StartupFinding(
                    "ORDER_RECONCILIATION_FAILED",
                    "broker/internal order reconciliation did not complete",
                )
            )
            return StartupReport(
                StartupStage.BLOCKED, Readiness.BLOCKED, tuple(findings)
            )

        if not self.deps.reconcile_positions():
            findings.append(
                StartupFinding(
                    "POSITION_RECONCILIATION_FAILED",
                    "broker/internal position reconciliation did not complete",
                )
            )
            return StartupReport(
                StartupStage.BLOCKED, Readiness.BLOCKED, tuple(findings)
            )

        return StartupReport(
            StartupStage.READY,
            Readiness.READY,
            tuple(findings),
        )
