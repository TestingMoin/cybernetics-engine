from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlparse
from typing import Any, Callable, Protocol


class PostgreSQLConfigError(ValueError):
    """Raised when PostgreSQL staging configuration is invalid."""


class ConnectionStatus(str, Enum):
    NOT_CONFIGURED = "NOT_CONFIGURED"
    READY = "READY"
    FAILED = "FAILED"


@dataclass(frozen=True)
class PostgreSQLStagingConfig:
    """Validated PostgreSQL connection settings without storing a password in logs."""

    dsn: str
    connect_timeout_seconds: float = 5.0
    application_name: str = "cybernetics-engine"

    @classmethod
    def from_env(cls, environ: dict[str, str] | None = None) -> "PostgreSQLStagingConfig | None":
        import os

        env = os.environ if environ is None else environ
        dsn = (env.get("CYBERNETICS_POSTGRES_DSN") or "").strip()
        if not dsn:
            return None
        timeout_raw = env.get("CYBERNETICS_POSTGRES_CONNECT_TIMEOUT", "5")
        try:
            timeout = float(timeout_raw)
        except ValueError as exc:
            raise PostgreSQLConfigError("invalid_postgres_connect_timeout") from exc
        if timeout <= 0:
            raise PostgreSQLConfigError("postgres_connect_timeout_must_be_positive")
        return cls(
            dsn=validate_dsn(dsn),
            connect_timeout_seconds=timeout,
            application_name=(env.get("CYBERNETICS_POSTGRES_APPLICATION_NAME") or "cybernetics-engine").strip(),
        )

    @property
    def redacted_dsn(self) -> str:
        parsed = urlparse(self.dsn)
        if parsed.scheme.startswith("postgres") and parsed.hostname:
            auth = parsed.hostname
            if parsed.port:
                auth += f":{parsed.port}"
            return f"{parsed.scheme}://{auth}{parsed.path or ''}{('?' + parsed.query) if parsed.query else ''}"
        return "[REDACTED]"



def psycopg_connector(dsn: str, connect_timeout_seconds: float, application_name: str) -> Connection:
    """Create a real PostgreSQL connection using Psycopg 3.

    Psycopg is imported lazily so the core package can still be imported in
    environments where the concrete PostgreSQL runtime dependency is absent.
    The deployment package declares ``psycopg[binary]`` as its production
    dependency, so this function is the concrete staging transport boundary.
    """
    try:
        import psycopg
    except ImportError as exc:
        raise PostgreSQLConfigError("psycopg_driver_missing") from exc

    return psycopg.connect(
        dsn,
        connect_timeout=connect_timeout_seconds,
        application_name=application_name,
    )


def psycopg_connection_factory(config: PostgreSQLStagingConfig) -> Callable[[], Connection]:
    """Return a connection factory suitable for durable repositories/audit sinks."""
    if config is None:
        raise PostgreSQLConfigError("postgres_config_required")
    return lambda: psycopg_connector(
        config.dsn,
        config.connect_timeout_seconds,
        config.application_name,
    )


def validate_dsn(dsn: str) -> str:
    value = dsn.strip()
    if not value:
        raise PostgreSQLConfigError("postgres_dsn_required")
    parsed = urlparse(value)
    if parsed.scheme not in {"postgresql", "postgres"}:
        raise PostgreSQLConfigError("postgres_dsn_scheme_invalid")
    if not parsed.hostname:
        raise PostgreSQLConfigError("postgres_dsn_host_required")
    if not parsed.path or parsed.path == "/":
        raise PostgreSQLConfigError("postgres_dsn_database_required")
    if any(secret in value.lower() for secret in ("password=", "passwd=")) and "@" not in value:
        raise PostgreSQLConfigError("postgres_dsn_invalid")
    return value


class Connection(Protocol):
    def execute(self, query: str) -> Any: ...
    def close(self) -> None: ...


Connector = Callable[[str, float, str], Connection]


@dataclass(frozen=True)
class PostgreSQLStagingProbe:
    """Injected connector boundary for PostgreSQL staging readiness.

    Production code can supply a psycopg-based connector without coupling the
    core package to a specific driver. No connection is made when no DSN exists.
    """

    config: PostgreSQLStagingConfig | None
    connector: Connector | None = None

    def status(self) -> ConnectionStatus:
        if self.config is None:
            return ConnectionStatus.NOT_CONFIGURED
        if self.connector is None:
            return ConnectionStatus.FAILED
        connection: Connection | None = None
        try:
            connection = self.connector(
                self.config.dsn,
                self.config.connect_timeout_seconds,
                self.config.application_name,
            )
            connection.execute("SELECT 1")
            return ConnectionStatus.READY
        except Exception:
            return ConnectionStatus.FAILED
        finally:
            if connection is not None:
                try:
                    connection.close()
                except Exception:
                    pass

    def ready(self) -> bool:
        return self.status() is ConnectionStatus.READY
