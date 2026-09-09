from __future__ import annotations
from dataclasses import dataclass
from .store import Candle, CanonicalMarketStateStore

@dataclass(frozen=True)
class MergeReport:
    inserted:int
    duplicates:int
    conflicts:int
    ready:bool

def merge_recovered_candles(store:CanonicalMarketStateStore,
                            candles:list[Candle])->MergeReport:
    counts=store.merge(candles)
    return MergeReport(
        inserted=counts["INSERTED"],
        duplicates=counts["DUPLICATE"],
        conflicts=counts["CONFLICT"],
        ready=counts["CONFLICT"]==0,
    )
