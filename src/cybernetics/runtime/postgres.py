from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from cybernetics.brokers.interface import BrokerAdapter
from cybernetics.reconcile.dhan_runtime import DhanPostgresReconciliationAdapter

from cybernetics.db.staging import PostgreSQLStagingConfig, psycopg_connection_factory
from cybernetics.persistence.migration import PRODUCTION_STARTUP_REQUIRED_TABLES


@dataclass(frozen=True)
class PostgreSQLRuntimeAdapter:
    """Concrete PostgreSQL staging adapter used by the canonical runtime.

    The adapter performs only health/schema inspection. It does not submit
    broker orders and it does not infer broker/internal reconciliation without
    a broker-side reconciliation adapter. Those gates therefore remain blocked
    until the real Dhan adapter is connected.
    """

    config: PostgreSQLStagingConfig
    broker: BrokerAdapter | None = None
    reconciliation_cache_seconds: float = 10.0
    _reconciliation: DhanPostgresReconciliationAdapter | None = field(init=False, default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.reconciliation_cache_seconds <= 0:
            raise ValueError("reconciliation_cache_seconds_must_be_positive")
        if self.broker is not None:
            object.__setattr__(
                self,
                "_reconciliation",
                DhanPostgresReconciliationAdapter(
                    broker=self.broker,
                    connection_factory=psycopg_connection_factory(self.config),
                    reconciliation_cache_seconds=self.reconciliation_cache_seconds,
                ),
            )

    def _connection(self):
        return psycopg_connection_factory(self.config)()

    def health_check(self) -> bool:
        connection = None
        try:
            connection = self._connection()
            connection.execute("SELECT 1")
            return True
        except Exception:
            return False
        finally:
            if connection is not None:
                try:
                    connection.close()
                except Exception:
                    pass

    def existing_tables(self) -> set[str]:
        connection = self._connection()
        try:
            rows = connection.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                """
            ).fetchall()
            return {str(row[0]) for row in rows}
        finally:
            connection.close()

    def migration_version(self) -> int:
        connection = self._connection()
        try:
            row = connection.execute(
                "SELECT COALESCE(MAX(version), 0) FROM schema_version"
            ).fetchone()
            return int(row[0]) if row is not None else 0
        finally:
            connection.close()

    def persistence_ready(self) -> bool:
        try:
            if not self.health_check():
                return False
            tables = self.existing_tables()
            return set(PRODUCTION_STARTUP_REQUIRED_TABLES).issubset(tables)
        except Exception:
            return False

    # Conservative recovery boundary. Real broker/internal reconciliation is
    # deliberately withheld until the broker adapter is connected and can
    # compare both sides authoritatively.
    def validate_persistence(self) -> bool:
        return self.persistence_ready()

    def _reconciliation_adapter(self) -> DhanPostgresReconciliationAdapter | None:
        return self._reconciliation

    def find_unresolved_recovery_cases(self) -> Iterable[str]:
        return ()

    def reconcile_orders(self) -> bool:
        adapter = self._reconciliation_adapter()
        return bool(adapter and adapter.reconcile().orders_reconciled)

    def reconcile_positions(self) -> bool:
        adapter = self._reconciliation_adapter()
        return bool(adapter and adapter.reconcile().positions_reconciled)
