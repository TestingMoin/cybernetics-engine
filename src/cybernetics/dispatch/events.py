from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Any

@dataclass(frozen=True)
class MarketEvent:
    security_id: str
    exchange_segment: str
    event_type: str
    timestamp: datetime
    payload: dict[str, Any]
    timeframe: str | None = None

    def __post_init__(self):
        if not self.security_id or not self.exchange_segment or not self.event_type:
            raise ValueError("market_event_identity_required")
        if not isinstance(self.payload, dict):
            raise ValueError("market_event_payload_must_be_dict")
