from __future__ import annotations
from dataclasses import dataclass
from typing import Literal, Optional

Regime = Literal["TREND_UP", "TREND_DOWN", "RANGE", "HIGH_VOL", "LOW_VOL", "UNKNOWN"]

@dataclass(frozen=True)
class RegimeSnapshot:
    regime: Regime
    trend_score: float
    volatility_score: float
    confidence: float
    reasons: tuple[str, ...]

class MarketRegimeEngine:
    """Deterministic baseline regime classifier. It does not generate orders."""

    def classify(self, *, close: float, ema_fast: Optional[float],
                 ema_slow: Optional[float], atr_value: Optional[float],
                 atr_baseline: Optional[float]) -> RegimeSnapshot:
        reasons: list[str] = []
        if close <= 0:
            return RegimeSnapshot("UNKNOWN", 0.0, 0.0, 0.0, ("invalid_close",))

        trend_score = 0.0
        if ema_fast is not None and ema_slow is not None:
            if ema_fast > ema_slow:
                trend_score = min(1.0, (ema_fast - ema_slow) / close * 100.0)
                reasons.append("fast_ema_above_slow")
            elif ema_fast < ema_slow:
                trend_score = max(-1.0, (ema_fast - ema_slow) / close * 100.0)
                reasons.append("fast_ema_below_slow")

        vol_score = 0.0
        if atr_value is not None and atr_baseline and atr_baseline > 0:
            vol_score = atr_value / atr_baseline
            if vol_score >= 1.5:
                reasons.append("atr_high")
                return RegimeSnapshot("HIGH_VOL", trend_score, vol_score, 0.9, tuple(reasons))
            if vol_score <= 0.6:
                reasons.append("atr_low")
                return RegimeSnapshot("LOW_VOL", trend_score, vol_score, 0.8, tuple(reasons))

        if trend_score >= 0.001:
            return RegimeSnapshot("TREND_UP", trend_score, vol_score, 0.7, tuple(reasons))
        if trend_score <= -0.001:
            return RegimeSnapshot("TREND_DOWN", trend_score, vol_score, 0.7, tuple(reasons))
        return RegimeSnapshot("RANGE", trend_score, vol_score, 0.6, tuple(reasons or ["flat_trend"]))
