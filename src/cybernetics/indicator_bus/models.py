from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class CandleInput:
    security_id: str
    timeframe: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0

    def __post_init__(self):
        if not self.security_id or not self.timeframe:
            raise ValueError("candle_identity_required")
        if min(self.open, self.high, self.low, self.close) < 0:
            raise ValueError("negative_candle_price")
        if self.high < max(self.open, self.close):
            raise ValueError("invalid_candle_high")
        if self.low > min(self.open, self.close):
            raise ValueError("invalid_candle_low")
        if self.volume < 0:
            raise ValueError("negative_candle_volume")

@dataclass(frozen=True)
class IndicatorSnapshot:
    security_id: str
    timeframe: str
    timestamp: datetime
    values: dict[str, float | None]
    ready: tuple[str, ...]
