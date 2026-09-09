from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import FrozenSet


class ContractViolation(ValueError):
    """Raised when a module integration contract is incomplete or invalid."""


class IntegrationLayer(str, Enum):
    CONTROL = "CONTROL"
    PERSISTENCE = "PERSISTENCE"
    MARKET_DATA = "MARKET_DATA"
    UNIVERSE = "UNIVERSE"
    SCANNERS = "SCANNERS"
    INDICATORS = "INDICATORS"
    SIGNALS = "SIGNALS"
    STRATEGY = "STRATEGY"
    RISK = "RISK"
    EXECUTION = "EXECUTION"
    RECONCILIATION = "RECONCILIATION"
    RECOVERY = "RECOVERY"
    OBSERVABILITY = "OBSERVABILITY"


@dataclass(frozen=True)
class ModuleContract:
    module_id: str
    layer: IntegrationLayer
    version: str
    provides: FrozenSet[str]
    requires: FrozenSet[str]
    production_eligible: bool = False

    def __post_init__(self):
        if not self.module_id:
            raise ContractViolation("module_id_required")
        if not self.version:
            raise ContractViolation("version_required")
        if not self.provides:
            raise ContractViolation("provides_required")
        if self.provides & self.requires:
            raise ContractViolation("self_dependency_not_allowed")


@dataclass(frozen=True)
class ContractIssue:
    module_id: str
    code: str
    detail: str
    blocking: bool = True


@dataclass(frozen=True)
class IntegrationReport:
    ready: bool
    issues: tuple[ContractIssue, ...]


class DependencyAuditor:
    """Static contract auditor; it does not import or execute the modules."""

    def audit(self, contracts: tuple[ModuleContract, ...]) -> IntegrationReport:
        issues: list[ContractIssue] = []
        ids: set[str] = set()

        for contract in contracts:
            if contract.module_id in ids:
                issues.append(
                    ContractIssue(
                        contract.module_id,
                        "DUPLICATE_MODULE_ID",
                        "module_id is declared by more than one contract",
                    )
                )
            ids.add(contract.module_id)

        providers: dict[str, list[str]] = {}
        for contract in contracts:
            for capability in contract.provides:
                providers.setdefault(capability, []).append(contract.module_id)

        for contract in contracts:
            for requirement in contract.requires:
                owners = providers.get(requirement, [])
                if not owners:
                    issues.append(
                        ContractIssue(
                            contract.module_id,
                            "MISSING_PROVIDER",
                            f"required capability not provided: {requirement}",
                        )
                    )
                elif len(owners) > 1:
                    issues.append(
                        ContractIssue(
                            contract.module_id,
                            "AMBIGUOUS_PROVIDER",
                            f"multiple providers for capability {requirement}: {owners}",
                        )
                    )

        return IntegrationReport(not any(i.blocking for i in issues), tuple(issues))


CORE_CONTRACTS = (
    ModuleContract(
        "control",
        IntegrationLayer.CONTROL,
        "1",
        frozenset({"control.commands", "control.state"}),
        frozenset(),
        False,
    ),
    ModuleContract(
        "postgres-persistence",
        IntegrationLayer.PERSISTENCE,
        "1",
        frozenset({
            "persistence.fill_ledger",
            "persistence.fill_outbox",
            "persistence.control_audit",
        }),
        frozenset(),
        False,
    ),
    ModuleContract(
        "market-data",
        IntegrationLayer.MARKET_DATA,
        "1",
        frozenset({"market.canonical_state", "market.data_ready"}),
        frozenset(),
        False,
    ),
    ModuleContract(
        "universe",
        IntegrationLayer.UNIVERSE,
        "1",
        frozenset({"universe.active_instruments"}),
        frozenset(),
        False,
    ),
    ModuleContract(
        "scanners",
        IntegrationLayer.SCANNERS,
        "1",
        frozenset({"scanner.qualified_signals", "scanner.health"}),
        frozenset({"market.canonical_state", "universe.active_instruments"}),
        False,
    ),
    ModuleContract(
        "signals",
        IntegrationLayer.SIGNALS,
        "1",
        frozenset({"signal.qualified"}),
        frozenset({"scanner.qualified_signals", "market.data_ready"}),
        False,
    ),
    ModuleContract(
        "strategy-risk",
        IntegrationLayer.STRATEGY,
        "1",
        frozenset({"strategy.risk_request"}),
        frozenset({"signal.qualified"}),
        False,
    ),
    ModuleContract(
        "risk",
        IntegrationLayer.RISK,
        "1",
        frozenset({"risk.approved_request", "risk.sizing"}),
        frozenset({"strategy.risk_request"}),
        False,
    ),
    ModuleContract(
        "execution",
        IntegrationLayer.EXECUTION,
        "1",
        frozenset({"execution.intent"}),
        frozenset({
            "risk.approved_request",
            "universe.active_instruments",
            "control.state",
        }),
        False,
    ),
    ModuleContract(
        "reconciliation-recovery",
        IntegrationLayer.RECONCILIATION,
        "1",
        frozenset({"reconciliation.ready", "recovery.clear"}),
        frozenset({
            "persistence.fill_ledger",
            "persistence.control_audit",
        }),
        False,
    ),
)
