from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal
import time, uuid

Side=Literal["LONG","SHORT","NEUTRAL"]

@dataclass(frozen=True)
class SignalContext:
    signal_id: str
    timestamp: float
    exchange: str
    scanner_id: str
    instrument: str
    underlying: str
    timeframe: str
    side: Side
    source: str
    score: float
    confidence: float
    regime: str|None=None
    evidence: tuple[str,...]=()
    invalidations: tuple[str,...]=()
    ttl_seconds: float=60.0
    metadata: dict[str,Any]=field(default_factory=dict)
    @property
    def expires_at(self): return self.timestamp+self.ttl_seconds
    def is_expired(self,now=None): return (time.time() if now is None else now)>=self.expires_at

class SignalState(str,Enum):
    OBSERVED="OBSERVED"; ACTIVE="ACTIVE"; INVALIDATED="INVALIDATED"; EXPIRED="EXPIRED"

@dataclass(frozen=True)
class SignalRecord:
    signal_id:str
    scanner_id:str
    underlying_key:str
    timeframe:str
    timestamp:object
    signal_type:str
    direction:str|None
    strength:float
    evidence:dict=field(default_factory=dict)
    state:SignalState=SignalState.OBSERVED
    def __post_init__(self):
        if not self.signal_id or not self.scanner_id or not self.underlying_key:
            raise ValueError("signal_identity_required")
        if not 0<=self.strength<=1:
            raise ValueError("signal_strength_out_of_range")

class SignalRegistry:
    def __init__(self,max_signals_per_key=100):
        self._signals={}
        self._items={}
        self.max_signals_per_key=max_signals_per_key
    def publish(self,signal):
        key=f"{signal.exchange}:{signal.scanner_id}:{signal.instrument}"
        bucket=self._signals.setdefault(key,[])
        bucket.append(signal)
        if len(bucket)>self.max_signals_per_key: del bucket[:-self.max_signals_per_key]
    def recent(self,exchange,scanner_id,instrument,now=None):
        key=f"{exchange}:{scanner_id}:{instrument}"
        cur=time.time() if now is None else now
        return [s for s in self._signals.get(key,[]) if not s.is_expired(cur)]
    def clear_expired(self,now=None):
        cur=time.time() if now is None else now
        removed=0
        for key in list(self._signals):
            old=len(self._signals[key])
            self._signals[key]=[s for s in self._signals[key] if not s.is_expired(cur)]
            removed+=old-len(self._signals[key])
            if not self._signals[key]: del self._signals[key]
        return removed
    def count(self):
        return sum(len(v) for v in self._signals.values()) + len(self._items)
    def register(self,signal):
        if signal.signal_id in self._items: raise ValueError("duplicate_signal_id")
        self._items[signal.signal_id]=signal
        return signal
    def get(self,signal_id):
        if signal_id not in self._items: raise KeyError("signal_not_found")
        return self._items[signal_id]
    def list(self): return list(self._items.values())

def make_signal(**kwargs):
    kwargs=dict(kwargs)
    kwargs.setdefault("timestamp",time.time())
    kwargs.setdefault("signal_id",str(uuid.uuid4()))
    return SignalContext(**kwargs)
