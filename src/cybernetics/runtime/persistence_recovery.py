from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Protocol, Set

from cybernetics.persistence.migration import StartupSchemaValidator
from cybernetics.recovery.startup import (
    Readiness,
    StartupRecoveryDependencies,
    StartupRecoveryOrchestrator,
    StartupReport,
)


class ExistingTablesProvider(Protocol):
    def __call__(self) -> Set[str]: ...


class MigrationVersionProvider(Protocol):
    def __call__(self) -> int: ...


@dataclass(frozen=True)
class PostgreSQLPersistenceHealth:
    """Side-effect-free persistence readiness facade over canonical schema state."""

    existing_tables: ExistingTablesProvider
    migration_version: MigrationVersionProvider
    validator: StartupSchemaValidator = StartupSchemaValidator()

    def check(self) -> bool:
        report = self.validator.validate_production(
            existing_tables=set(self.existing_tables()),
            migration_version=int(self.migration_version()),
        )
        return report.ready


@dataclass(frozen=True)
class PersistenceRecoveryRuntimeWiring:
    """Runtime bridge for persistence validation and startup recovery.

    The bridge invokes only injected providers/orchestrators. It owns no DB
    pool, credentials, broker client, or order-submission path.
    """

    persistence_health: PostgreSQLPersistenceHealth
    recovery: StartupRecoveryOrchestrator

    def startup_report(self) -> StartupReport:
        return self.recovery.run()

    def persistence_ready(self) -> bool:
        return self.persistence_health.check()

    def recovery_clear(self) -> bool:
        report = self.startup_report()
        return report.readiness is Readiness.READY

    def orders_reconciled(self) -> bool:
        report = self.startup_report()
        return report.readiness is Readiness.READY and not any(
            finding.code == "ORDER_RECONCILIATION_FAILED"
            for finding in report.findings
        )

    def positions_reconciled(self) -> bool:
        report = self.startup_report()
        return report.readiness is Readiness.READY and not any(
            finding.code == "POSITION_RECONCILIATION_FAILED"
            for finding in report.findings
        )

    def runtime_readiness(self) -> dict[str, bool]:
        report = self.startup_report()
        ready = report.readiness is Readiness.READY and self.persistence_health.check()
        return {
            "persistence_ready": self.persistence_health.check(),
            "recovery_clear": ready,
            "orders_reconciled": ready,
            "positions_reconciled": ready,
        }


def build_persistence_recovery_wiring(
    *,
    existing_tables: ExistingTablesProvider,
    migration_version: MigrationVersionProvider,
    startup_dependencies: StartupRecoveryDependencies,
) -> PersistenceRecoveryRuntimeWiring:
    """Create the canonical persistence/recovery runtime bridge."""

    health = PostgreSQLPersistenceHealth(
        existing_tables=existing_tables,
        migration_version=migration_version,
    )
    orchestrator = StartupRecoveryOrchestrator(startup_dependencies)
    return PersistenceRecoveryRuntimeWiring(
        persistence_health=health,
        recovery=orchestrator,
    )
