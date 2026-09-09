from __future__ import annotations
from dataclasses import dataclass, replace
from datetime import datetime
from threading import RLock
from typing import Optional

@dataclass(frozen=True)
class Candle:
    security_id: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    source: str = "LIVE"

    def __post_init__(self):
        if min(self.open, self.high, self.low, self.close) < 0:
            raise ValueError("negative_candle_price")
        if self.high < max(self.open, self.close):
            raise ValueError("invalid_candle_high")
        if self.low > min(self.open, self.close):
            raise ValueError("invalid_candle_low")
        if self.volume < 0:
            raise ValueError("negative_candle_volume")

class CanonicalMarketStateStore:
    """
    Single authoritative candle store keyed by (security_id, timestamp).

    Merge policy:
    - Same key + same values: idempotent duplicate, ignored.
    - Same key + different values: retained as conflict; existing canonical value
      is not overwritten automatically.
    - New key: inserted.
    """
    def __init__(self):
        self._candles: dict[tuple[str,datetime], Candle] = {}
        self._conflicts: dict[tuple[str,datetime], list[Candle]] = {}
        self._lock=RLock()

    def upsert(self, candle:Candle) -> str:
        key=(candle.security_id,candle.timestamp)
        with self._lock:
            current=self._candles.get(key)
            if current is None:
                self._candles[key]=candle
                return "INSERTED"
            if current == candle:
                return "DUPLICATE"
            self._conflicts.setdefault(key,[]).append(candle)
            return "CONFLICT"

    def merge(self, candles:list[Candle]) -> dict[str,int]:
        counts={"INSERTED":0,"DUPLICATE":0,"CONFLICT":0}
        with self._lock:
            for candle in candles:
                counts[self.upsert(candle)] += 1
        return counts

    def get(self, security_id:str, timestamp:datetime) -> Optional[Candle]:
        with self._lock:
            return self._candles.get((security_id,timestamp))

    def recent(self, security_id:str, limit:int=100)->list[Candle]:
        if limit<=0: return []
        with self._lock:
            rows=[c for (sid,_),c in self._candles.items() if sid==security_id]
        return sorted(rows,key=lambda c:c.timestamp)[-limit:]

    def conflicts(self, security_id:Optional[str]=None)->list[tuple[tuple[str,datetime],list[Candle]]]:
        with self._lock:
            items=list(self._conflicts.items())
        if security_id is None:
            return items
        return [x for x in items if x[0][0]==security_id]

    def last_timestamp(self, security_id:str)->Optional[datetime]:
        rows=self.recent(security_id,1)
        return rows[-1].timestamp if rows else None
