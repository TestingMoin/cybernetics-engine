from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class IchimokuSnapshot:
    conversion: Optional[float]
    base: Optional[float]
    span_a: Optional[float]
    span_b: Optional[float]
    lagging: Optional[float]

class IchimokuEngine:
    """Standard Ichimoku calculation with explicit windows; no trading signal."""

    def compute(self, bars, conversion_len=9, base_len=26, span_b_len=52,
                displacement=26) -> IchimokuSnapshot:
        def mid(window):
            if len(bars) < window: return None
            w=bars[-window:]
            return (max(x.high for x in w)+min(x.low for x in w))/2.0
        conv=mid(conversion_len); base=mid(base_len); sb=mid(span_b_len)
        sa=None if conv is None or base is None else (conv+base)/2.0
        lag=None if len(bars)<=displacement else bars[-1-displacement].close
        return IchimokuSnapshot(conv,base,sa,sb,lag)
