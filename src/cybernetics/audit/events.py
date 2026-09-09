from dataclasses import dataclass
from typing import Any
import uuid, json, time

@dataclass(frozen=True)
class AuditEvent:
    event_id: str
    event_ts: float
    event_type: str
    severity: str
    source: str
    payload: dict[str, Any]

class AuditEventFactory:
    def create(self, event_type: str, source: str, payload: dict[str,Any],
               severity: str="INFO") -> AuditEvent:
        return AuditEvent(str(uuid.uuid4()), time.time(), event_type, severity, source, payload)

class InMemoryAuditStore:
    """
    Test/reference store. Production persistence targets PostgreSQL via the SQL schema.
    """
    def __init__(self):
        self.events: list[AuditEvent] = []

    def append(self, event: AuditEvent) -> None:
        self.events.append(event)

    def by_type(self, event_type: str) -> list[AuditEvent]:
        return [e for e in self.events if e.event_type == event_type]

    def count(self) -> int:
        return len(self.events)
