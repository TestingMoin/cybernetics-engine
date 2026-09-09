from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol
import json

from .events import AuditEvent, AuditEventFactory


class AuditSink(Protocol):
    def append(self, event: AuditEvent) -> None: ...


class PostgresEngineEventRepository:
    """Durable sink for the canonical PostgreSQL engine_events table."""

    def __init__(self, connection_factory: Callable[[], object]) -> None:
        self.connection_factory = connection_factory

    def append(self, event: AuditEvent) -> None:
        correlation_id = event.payload.get("correlation_id")
        payload = dict(event.payload)
        payload.pop("correlation_id", None)
        with self.connection_factory() as tx:
            tx.execute(
                """
                INSERT INTO engine_events(
                    event_id,event_ts,event_type,severity,source,correlation_id,payload
                ) VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb)
                ON CONFLICT (event_id) DO NOTHING
                """.strip(),
                (
                    event.event_id,
                    event.event_ts,
                    event.event_type,
                    event.severity,
                    event.source,
                    correlation_id,
                    json.dumps(payload, sort_keys=True),
                ),
            )


@dataclass
class RuntimeAuditEmitter:
    """Emits lifecycle/readiness events without owning runtime decisions."""

    sink: AuditSink
    factory: AuditEventFactory | None = None
    source: str = "runtime"

    def __post_init__(self) -> None:
        if self.factory is None:
            self.factory = AuditEventFactory()

    def emit(self, event_type: str, payload: dict, *, severity: str = "INFO") -> AuditEvent:
        event = self.factory.create(event_type, self.source, payload, severity=severity)
        self.sink.append(event)
        return event

    def lifecycle(self, state: str, *, previous: str | None = None) -> AuditEvent:
        payload = {"state": state}
        if previous is not None:
            payload["previous_state"] = previous
        return self.emit("RUNTIME_LIFECYCLE", payload)

    def readiness(self, *, engine_ready: bool, new_trades_allowed: bool, reason: str) -> AuditEvent:
        return self.emit(
            "RUNTIME_READINESS",
            {
                "engine_ready": bool(engine_ready),
                "new_trades_allowed": bool(new_trades_allowed),
                "reason": reason,
            },
        )


__all__ = ["AuditSink", "PostgresEngineEventRepository", "RuntimeAuditEmitter"]
