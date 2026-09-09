from __future__ import annotations


class InMemoryCommandIdStore:
    """Test/local implementation; production should use durable idempotency."""

    def __init__(self):
        self._ids: set[str] = set()

    def seen(self, command_id: str) -> bool:
        return command_id in self._ids

    def remember(self, command_id: str) -> None:
        self._ids.add(command_id)


class InMemoryAuditSink:
    def __init__(self):
        self.events: list[dict[str, object]] = []

    def record(self, **event):
        self.events.append(dict(event))
