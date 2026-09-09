from __future__ import annotations
from dataclasses import dataclass
from typing import Callable

from .events import AuditEvent
from .runtime import AuditSink, RuntimeAuditEmitter

@dataclass
class HealthAuditEmitter:
    """Emit health events only when a component's observable state changes."""
    sink: AuditSink
    source: str = "health"
    _last: dict[str, tuple[str, str, float | None]] | None = None

    def __post_init__(self) -> None:
        if self._last is None:
            self._last = {}

    def observe_registry(self, registry, *, names=None) -> list[AuditEvent]:
        events: list[AuditEvent] = []
        selected = list(names) if names is not None else [s.name for s in registry.all()]
        for name in selected:
            state = registry.get(name)
            key = (state.health.value, state.detail, state.last_heartbeat)
            prior = self._last.get(name)
            if prior == key:
                continue
            self._last[name] = key
            payload = {
                "component": name,
                "health": state.health.value,
                "detail": state.detail,
                "last_heartbeat": state.last_heartbeat,
                "metadata": dict(state.metadata),
            }
            event = RuntimeAuditEmitter(self.sink, source=self.source).emit(
                "COMPONENT_HEALTH",
                payload,
                severity="ERROR" if state.health.value == "FAILED" else "WARN" if state.health.value in {"DEGRADED", "UNKNOWN"} else "INFO",
            )
            events.append(event)
        return events

    def emit_feed_state(self, shard_id: int, state: str, *, detail: str = "", timestamp=None) -> AuditEvent | None:
        name = f"feed_shard:{shard_id}"
        key = (str(state), detail, timestamp)
        if self._last.get(name) == key:
            return None
        self._last[name] = key
        return RuntimeAuditEmitter(self.sink, source=self.source).emit(
            "FEED_HEALTH",
            {"shard_id": int(shard_id), "state": str(state), "detail": detail, "timestamp": timestamp},
            severity="ERROR" if str(state) in {"DISCONNECTED", "STALE"} else "WARN" if str(state) in {"DEGRADED", "UNKNOWN"} else "INFO",
        )

__all__ = ["HealthAuditEmitter"]
