from __future__ import annotations

from importlib import resources
from pathlib import Path


def schema_sql() -> str:
    return (
        resources.files("cybernetics.db")
        .joinpath("schema.sql")
        .read_text(encoding="utf-8")
    )


def schema_path() -> Path:
    """Return a materialized filesystem path for the packaged schema.

    When installed as a normal wheel, the package resource is available through
    importlib.resources.  The returned temporary path remains valid for the
    lifetime of the context created by callers that need a filesystem handle;
    callers should prefer schema_sql() when possible.
    """
    resource = resources.files("cybernetics.db").joinpath("schema.sql")
    return Path(resource)
