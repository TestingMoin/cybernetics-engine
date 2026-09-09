from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from .indicators import Bar, ema, rsi, atr, bollinger, roc
from .regime import MarketRegimeEngine, RegimeSnapshot

@dataclass
class IndicatorState:
    ema5: Optional[float] = None
    ema15: Optional[float] = None
    rsi14: Optional[float] = None
    atr14: Optional[float] = None
    bb20: Optional[dict] = None
    roc12: Optional[float] = None
    regime: Optional[RegimeSnapshot] = None

class AnalyticsStateEngine:
    def __init__(self, regime_engine: Optional[MarketRegimeEngine] = None):
        self.regime_engine = regime_engine or MarketRegimeEngine()

    def compute(self, bars: list[Bar], atr_baseline: Optional[float] = None) -> IndicatorState:
        closes = [b.close for b in bars]
        e5 = ema(closes, 5)
        e15 = ema(closes, 15)
        a14 = atr(bars, 14)
        state = IndicatorState(
            ema5=e5,
            ema15=e15,
            rsi14=rsi(bars, 14),
            atr14=a14,
            bb20=bollinger(bars, 20, 2.0),
            roc12=roc(bars, 12),
        )
        state.regime = self.regime_engine.classify(
            close=bars[-1].close if bars else 0,
            ema_fast=e5,
            ema_slow=e15,
            atr_value=a14,
            atr_baseline=atr_baseline,
        )
        return state
