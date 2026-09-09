from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta
from .store import CanonicalMarketStateStore, Candle

class StateStatus(str, Enum):
    CONSISTENT="CONSISTENT"
    LIVE_AHEAD="LIVE_AHEAD"
    REST_AHEAD="REST_AHEAD"
    CONFLICT="CONFLICT"
    INCOMPLETE="INCOMPLETE"

@dataclass(frozen=True)
class ReconcileResult:
    security_id:str
    status:StateStatus
    live_last:datetime|None
    rest_last:datetime|None
    missing_live:int
    missing_rest:int
    conflicts:int

class StateReconciler:
    """
    Compares a live-derived candle set with a REST-derived snapshot.

    It reports disagreement; it never silently overwrites canonical state.
    """
    def __init__(self, store:CanonicalMarketStateStore):
        self.store=store

    def reconcile(self, security_id:str,
                  live:list[Candle], rest:list[Candle],
                  tolerance:timedelta=timedelta(0))->ReconcileResult:
        live_map={(c.security_id,c.timestamp):c for c in live if c.security_id==security_id}
        rest_map={(c.security_id,c.timestamp):c for c in rest if c.security_id==security_id}
        keys=set(live_map)|set(rest_map)
        missing_live=len(set(rest_map)-set(live_map))
        missing_rest=len(set(live_map)-set(rest_map))
        conflicts=0
        for k in set(live_map)&set(rest_map):
            a,b=live_map[k],rest_map[k]
            if not self._equivalent(a,b,tolerance):
                conflicts+=1
        live_last=max((c.timestamp for c in live_map.values()),default=None)
        rest_last=max((c.timestamp for c in rest_map.values()),default=None)

        if conflicts:
            status=StateStatus.CONFLICT
        elif missing_live and not missing_rest:
            status=StateStatus.REST_AHEAD
        elif missing_rest and not missing_live:
            status=StateStatus.LIVE_AHEAD
        elif missing_live or missing_rest:
            status=StateStatus.INCOMPLETE
        else:
            status=StateStatus.CONSISTENT

        return ReconcileResult(security_id,status,live_last,rest_last,
                               missing_live,missing_rest,conflicts)

    @staticmethod
    def _equivalent(a:Candle,b:Candle,tolerance:timedelta)->bool:
        # `tolerance` is reserved for future timestamp normalization; prices/volume
        # remain exact at this layer to avoid masking data-quality differences.
        if a.timestamp != b.timestamp:
            return False
        return (a.open==b.open and a.high==b.high and
                a.low==b.low and a.close==b.close and
                a.volume==b.volume)
