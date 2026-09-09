from __future__ import annotations
from dataclasses import dataclass
import math

@dataclass(frozen=True)
class GannCycle:
    anchor_index: int
    anchor_price: float
    period_bars: int
    phase: float
    cycle_ratio: float
    projected_price: float

class GannCycleDecoder:
    """
    Deterministic Gann-style cycle decoder.
    It encodes cyclical timing/angle relationships from supplied inputs;
    it does not infer institutional intent or generate orders.
    """

    def decode(self, anchor_index:int, anchor_price:float, current_index:int,
               period_bars:int, price_step:float=1.0) -> GannCycle:
        if anchor_price <= 0 or period_bars <= 0 or price_step <= 0:
            raise ValueError("invalid Gann cycle inputs")
        elapsed=current_index-anchor_index
        ratio=elapsed/period_bars
        phase=elapsed % period_bars / period_bars
        projected=anchor_price + (round(ratio)*price_step)
        return GannCycle(anchor_index,anchor_price,period_bars,phase,ratio,projected)

    def square_of_nine_level(self, price:float, roots:tuple[float,...]=(0.5,1.0,1.5,2.0)) -> tuple[float,...]:
        if price<=0: raise ValueError("price must be positive")
        r=math.sqrt(price)
        return tuple(round((r+x)**2,10) for x in roots)
