from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Iterable, Optional
from .models import ScannerRuntime, ScannerRuntimeKey, ScannerState

@dataclass(frozen=True)
class RegistryEvent:
    action: str
    key: ScannerRuntimeKey
    state: ScannerState

class ScannerRuntimeRegistry:
    """
    Owns isolated runtime instances.

    Isolation key:
        scanner_id + underlying_key + timeframe

    The registry deliberately stores a single runtime object per key. A scanner
    implementation can therefore be reused across many underlyings without
    shared mutable indicator/signal state.
    """
    def __init__(self, on_event: Optional[Callable[[RegistryEvent], None]] = None):
        self._items: dict[ScannerRuntimeKey, ScannerRuntime] = {}
        self._on_event = on_event

    def create(self, key: ScannerRuntimeKey, *, config_version: int = 1) -> ScannerRuntime:
        if key in self._items:
            raise ValueError("scanner_runtime_already_exists")
        if config_version <= 0:
            raise ValueError("invalid_config_version")
        runtime = ScannerRuntime(key=key, config_version=config_version)
        self._items[key] = runtime
        self._emit("CREATED", runtime)
        return runtime

    def get(self, key: ScannerRuntimeKey) -> ScannerRuntime:
        try:
            return self._items[key]
        except KeyError:
            raise KeyError("scanner_runtime_not_found")

    def get_or_create(self, key: ScannerRuntimeKey, *, config_version: int = 1) -> ScannerRuntime:
        return self._items.get(key) or self.create(key, config_version=config_version)

    def start(self, key: ScannerRuntimeKey) -> ScannerRuntime:
        r=self.get(key)
        if r.state not in {ScannerState.CREATED, ScannerState.STOPPED}:
            raise ValueError("scanner_runtime_not_startable")
        r.state=ScannerState.RUNNING
        self._emit("STARTED",r)
        return r

    def degrade(self, key: ScannerRuntimeKey, reason: str) -> ScannerRuntime:
        r=self.get(key)
        r.state=ScannerState.DEGRADED
        r.state_data["degraded_reason"]=reason
        self._emit("DEGRADED",r)
        return r

    def stop(self, key: ScannerRuntimeKey) -> ScannerRuntime:
        r=self.get(key)
        r.state=ScannerState.STOPPED
        self._emit("STOPPED",r)
        return r

    def fail(self, key: ScannerRuntimeKey, reason: str) -> ScannerRuntime:
        r=self.get(key)
        r.state=ScannerState.FAILED
        r.state_data["failure_reason"]=reason
        self._emit("FAILED",r)
        return r

    def remove(self, key: ScannerRuntimeKey) -> None:
        r=self.get(key)
        del self._items[key]
        self._emit("REMOVED",r)

    def list(self, *, scanner_id: Optional[str]=None,
             underlying_key: Optional[str]=None)->list[ScannerRuntime]:
        rows=list(self._items.values())
        if scanner_id is not None:
            rows=[r for r in rows if r.key.scanner_id==scanner_id]
        if underlying_key is not None:
            rows=[r for r in rows if r.key.underlying_key==underlying_key]
        return rows

    def count(self)->int:
        return len(self._items)

    def assert_isolated(self, keys: Iterable[ScannerRuntimeKey]) -> bool:
        key_list=list(keys)
        return len(key_list)==len(set(key_list))

    def _emit(self, action: str, runtime: ScannerRuntime)->None:
        if self._on_event:
            self._on_event(RegistryEvent(action,runtime.key,runtime.state))
