from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

@dataclass
class RuntimeIndicatorState:
    security_id: str
    timeframe: str
    values: dict[str, Any] = field(default_factory=dict)
    observation_count: int = 0
    last_timestamp: datetime | None = None

@dataclass(frozen=True)
class IndicatorBatchResult:
    security_id: str
    timeframe: str
    timestamp: datetime
    values: dict[str, Any]
    ready: tuple[str, ...]
