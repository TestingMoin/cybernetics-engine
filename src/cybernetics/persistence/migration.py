from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from cybernetics.db.schema import schema_path
from typing import Protocol, Sequence


# Authoritative schema source: project-root sql/schema.sql.
SCHEMA_PATH = schema_path()


class SQLExecutor(Protocol):
    def execute(self, sql: str) -> None: ...


@dataclass(frozen=True)
class SchemaVersion:
    version: int
    name: str


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    sql: str


@dataclass(frozen=True)
class StartupValidation:
    ready: bool
    missing_tables: tuple[str, ...]
    migration_version: int
    reason: str


# Keep these historical DDL names as compatibility metadata for the existing
# test/API surface. They do not own production schema creation anymore.


def load_authoritative_schema() -> str:
    if not SCHEMA_PATH.is_file():
        raise FileNotFoundError(f"authoritative_schema_missing: {SCHEMA_PATH}")
    return SCHEMA_PATH.read_text(encoding="utf-8")


# Compatibility metadata is loaded from the same canonical schema text.
_AUTHORITATIVE_SCHEMA_TEXT = load_authoritative_schema()
_CREATE_MARKER = "CREATE TABLE " + "IF NOT EXISTS"

def _table_ddl(table: str) -> str:
    marker = f"{_CREATE_MARKER} {table}"
    start = _AUTHORITATIVE_SCHEMA_TEXT.index(marker)
    next_start = _AUTHORITATIVE_SCHEMA_TEXT.find(_CREATE_MARKER, start + len(marker))
    chunk = _AUTHORITATIVE_SCHEMA_TEXT[start:] if next_start < 0 else _AUTHORITATIVE_SCHEMA_TEXT[start:next_start]
    return chunk

SCHEMA_VERSION_DDL = _table_ddl("schema_version")
FILL_LEDGER_DDL = _table_ddl("fill_ledger")
FILL_OUTBOX_DDL = _table_ddl("fill_outbox")


# Production migration history. Version 1 is the complete canonical baseline;
# subsequent versions are reserved for additive schema changes. This prevents
# separate modules from silently owning incompatible table definitions.
AUTHORITATIVE_MIGRATIONS = (
    Migration(1, "canonical_schema_baseline", load_authoritative_schema()),
)

# Additive migrations are kept separate from the immutable canonical baseline.
CONTROL_RECOVERY_AUDIT_MIGRATION = Migration(
    2,
    "control_recovery_audit",
    """
CREATE TABLE IF NOT EXISTS control_recovery_audit (
    event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL CHECK (event_type IN ('RECOVERY_OBSERVE','RECOVERY_RESUME')),
    phase TEXT NOT NULL,
    control_state TEXT NOT NULL,
    emergency_state TEXT NOT NULL,
    live_authorization_valid BOOLEAN NOT NULL,
    failures JSONB NOT NULL DEFAULT '[]'::jsonb,
    reason TEXT NOT NULL,
    actor TEXT NOT NULL,
    event_ts TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_control_recovery_audit_event_ts ON control_recovery_audit(event_ts);
CREATE INDEX IF NOT EXISTS idx_control_recovery_audit_phase ON control_recovery_audit(phase);
CREATE INDEX IF NOT EXISTS idx_control_recovery_audit_event_type ON control_recovery_audit(event_type);
""".strip()
)
ENGINE_EVENTS_AUDIT_MIGRATION = Migration(
    3,
    "engine_events_audit_boundary",
    """
-- engine_events already exists in the authoritative baseline (v1).
-- v3 formalizes its runtime-audit ownership without introducing a second table.
COMMENT ON TABLE engine_events IS 'Canonical durable runtime/engine audit stream; events are idempotent by event_id.';
""".strip(),
)

ADDITIVE_MIGRATIONS = (CONTROL_RECOVERY_AUDIT_MIGRATION, ENGINE_EVENTS_AUDIT_MIGRATION)


# Backward-compatible historical API retained for existing chunk tests. It is
# deliberately not used as the production migration chain.
MIGRATIONS = (
    Migration(1, "schema_version", SCHEMA_VERSION_DDL),
    Migration(2, "fill_ledger", FILL_LEDGER_DDL),
    Migration(3, "fill_outbox", FILL_OUTBOX_DDL),
)


STARTUP_REQUIRED_TABLES = ("fill_ledger", "fill_outbox")
PRODUCTION_STARTUP_REQUIRED_TABLES = (
    "schema_version", "orders", "fill_ledger", "fill_outbox",
    "control_command_audit", "emergency_control_state",
)


class MigrationRunner:
    """Deterministic migration boundary with explicit migration ordering."""

    def __init__(self, migrations: Sequence[Migration]):
        versions = [m.version for m in migrations]
        if len(versions) != len(set(versions)):
            raise ValueError("duplicate_migration_version")
        if versions != sorted(versions):
            raise ValueError("migrations_must_be_sorted")
        self.migrations = tuple(migrations)

    def pending(self, current_version: int) -> tuple[Migration, ...]:
        return tuple(m for m in self.migrations if m.version > current_version)

    def apply(self, executor: SQLExecutor, current_version: int) -> SchemaVersion:
        pending = self.pending(current_version)
        version = current_version
        name = "baseline"
        for migration in pending:
            executor.execute(migration.sql)
            version, name = migration.version, migration.name
        return SchemaVersion(version, name)


class StartupSchemaValidator:
    def validate(
        self,
        *,
        existing_tables: set[str],
        migration_version: int,
    ) -> StartupValidation:
        missing = tuple(t for t in STARTUP_REQUIRED_TABLES if t not in existing_tables)
        if missing:
            return StartupValidation(False, missing, migration_version, "required_persistence_tables_missing")
        return StartupValidation(True, (), migration_version, "persistence_schema_ready")

    def validate_production(
        self,
        *,
        existing_tables: set[str],
        migration_version: int,
    ) -> StartupValidation:
        missing = tuple(t for t in PRODUCTION_STARTUP_REQUIRED_TABLES if t not in existing_tables)
        if missing:
            return StartupValidation(False, missing, migration_version, "required_production_persistence_tables_missing")
        return StartupValidation(True, (), migration_version, "production_persistence_schema_ready")
