from __future__ import annotations
from dataclasses import dataclass
from threading import RLock
from typing import Optional

@dataclass(frozen=True)
class IdempotencyRecord:
    client_order_key: str
    broker_order_id: Optional[str]
    status: str

class IdempotencyBackend:
    def get(self,key: str) -> Optional[IdempotencyRecord]:
        raise NotImplementedError
    def put_once(self,record: IdempotencyRecord) -> bool:
        raise NotImplementedError
    def update(self,record: IdempotencyRecord) -> None:
        raise NotImplementedError

class IdempotencyStore(IdempotencyBackend):
    def __init__(self, backend: Optional[IdempotencyBackend]=None):
        self._backend=backend
        self._records={}
        self._lock=RLock()
    def get(self,key):
        if self._backend is not None: return self._backend.get(key)
        with self._lock: return self._records.get(key)
    def put_once(self,record):
        if self._backend is not None: return self._backend.put_once(record)
        with self._lock:
            if record.client_order_key in self._records: return False
            self._records[record.client_order_key]=record
            return True
    def update(self,record):
        if self._backend is not None: return self._backend.update(record)
        with self._lock:
            if record.client_order_key not in self._records:
                raise KeyError("unknown_client_order_key")
            self._records[record.client_order_key]=record
