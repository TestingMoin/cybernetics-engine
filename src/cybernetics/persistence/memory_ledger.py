from __future__ import annotations
from threading import RLock
from typing import Optional
from cybernetics.order_management.idempotency import IdempotencyRecord

class InMemoryOrderLedger:
    """Reference backend used by tests; not a production persistence layer."""
    def __init__(self):
        self._rows: dict[str, IdempotencyRecord] = {}
        self._lock = RLock()

    def get(self, key: str) -> Optional[IdempotencyRecord]:
        with self._lock:
            return self._rows.get(key)

    def put_once(self, record: IdempotencyRecord) -> bool:
        with self._lock:
            if record.client_order_key in self._rows:
                return False
            self._rows[record.client_order_key] = record
            return True

    def update(self, record: IdempotencyRecord) -> None:
        with self._lock:
            if record.client_order_key not in self._rows:
                raise KeyError("unknown_client_order_key")
            self._rows[record.client_order_key] = record
