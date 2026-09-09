from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Literal

GapType = Literal["GAP_UP","GAP_DOWN","NO_GAP"]
GapState = Literal["OPENING","PARTIAL","FILLED","CONTINUING","REJECTED","INVALID"]

@dataclass(frozen=True)
class GapSnapshot:
    underlying: str
    session_date: str
    prev_close: float
    open_price: float
    current_price: float
    gap_points: float
    gap_percent: float
    gap_type: GapType
    state: GapState
    fill_percent: float
    valid: bool
    reason: str

class GapEngine:
    """Deterministic opening-gap state machine; analytics only."""

    def evaluate(self, underlying: str, session_date: str, prev_close: float,
                 open_price: float, current_price: float,
                 tolerance_percent: float = 0.05) -> GapSnapshot:
        if min(prev_close, open_price, current_price) <= 0:
            return GapSnapshot(underlying,session_date,prev_close,open_price,current_price,
                               0,0,"NO_GAP","INVALID",0,False,"invalid_price")
        gap = open_price-prev_close
        pct = gap/prev_close*100
        if abs(pct) <= tolerance_percent:
            return GapSnapshot(underlying,session_date,prev_close,open_price,current_price,
                               gap,pct,"NO_GAP","OPENING",0,True,"within_tolerance")
        typ = "GAP_UP" if gap>0 else "GAP_DOWN"
        distance=abs(gap)
        move_toward_prev = (open_price-current_price) if gap>0 else (current_price-open_price)
        fill=max(0.0,min(100.0,move_toward_prev/distance*100))
        if fill>=100:
            state="FILLED"
        elif (gap>0 and current_price<open_price) or (gap<0 and current_price>open_price):
            state="REJECTED"
        elif fill>=50:
            state="PARTIAL"
        else:
            state="CONTINUING"
        return GapSnapshot(underlying,session_date,prev_close,open_price,current_price,
                           gap,pct,typ,state,fill,True,"observed_gap")
