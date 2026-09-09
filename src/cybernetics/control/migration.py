from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from cybernetics.db.schema import schema_path

_SCHEMA_PATH = schema_path()


CONTROL_COMMAND_AUDIT_DDL = _SCHEMA_PATH.read_text(encoding="utf-8") if _SCHEMA_PATH.is_file() else ""


@dataclass(frozen=True)
class ControlMigration:
    version: int
    name: str
    sql: str


CONTROL_MIGRATION = ControlMigration(
    4,
    "control_command_audit",
    CONTROL_COMMAND_AUDIT_DDL,
)
