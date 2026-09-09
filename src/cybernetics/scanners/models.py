from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

class ScannerState(str, Enum):
    CREATED="CREATED"
    STARTING="STARTING"
    RUNNING="RUNNING"
    DEGRADED="DEGRADED"
    STOPPED="STOPPED"
    FAILED="FAILED"

@dataclass(frozen=True)
class ScannerRuntimeKey:
    scanner_id: str
    underlying_key: str
    timeframe: str

    def __post_init__(self):
        if not self.scanner_id or not self.underlying_key or not self.timeframe:
            raise ValueError("scanner_runtime_key_required")

@dataclass
class ScannerRuntime:
    key: ScannerRuntimeKey
    config_version: int = 1
    state: ScannerState = ScannerState.CREATED
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_update_at: Optional[datetime] = None
    signal_count: int = 0
    event_count: int = 0
    state_data: dict[str, Any] = field(default_factory=dict)

    def update(self, *, signal_delta: int = 0, event_delta: int = 0,
               state_patch: Optional[dict[str, Any]] = None,
               when: Optional[datetime] = None) -> None:
        if signal_delta < 0 or event_delta < 0:
            raise ValueError("negative_runtime_counters")
        self.signal_count += signal_delta
        self.event_count += event_delta
        if state_patch:
            self.state_data.update(state_patch)
        self.last_update_at = when or datetime.now(timezone.utc)
