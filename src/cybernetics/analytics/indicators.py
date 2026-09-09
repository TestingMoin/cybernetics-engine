from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, Optional
import math

@dataclass(frozen=True)
class Bar:
    ts: float
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0

def _closes(bars: Iterable[Bar]) -> list[float]:
    return [float(b.close) for b in bars]

def sma(values: list[float], length: int) -> Optional[float]:
    if length <= 0 or len(values) < length:
        return None
    return sum(values[-length:]) / length

def ema(values: list[float], length: int) -> Optional[float]:
    if length <= 0 or len(values) < length:
        return None
    alpha = 2.0 / (length + 1.0)
    e = sum(values[:length]) / length
    for x in values[length:]:
        e = alpha * x + (1.0 - alpha) * e
    return e

def true_range(prev_close: Optional[float], bar: Bar) -> float:
    if prev_close is None:
        return bar.high - bar.low
    return max(bar.high - bar.low, abs(bar.high - prev_close), abs(bar.low - prev_close))

def atr(bars: list[Bar], length: int) -> Optional[float]:
    if length <= 0 or len(bars) < length:
        return None
    trs = []
    prev = None
    for b in bars:
        trs.append(true_range(prev, b))
        prev = b.close
    return sum(trs[-length:]) / length

def rsi(bars: list[Bar], length: int = 14) -> Optional[float]:
    if length <= 0 or len(bars) < length + 1:
        return None
    closes = _closes(bars)
    gains = []
    losses = []
    for a, b in zip(closes[-length-1:-1], closes[-length:]):
        d = b - a
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))
    avg_gain = sum(gains) / length
    avg_loss = sum(losses) / length
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))

def bollinger(bars: list[Bar], length: int = 20, mult: float = 2.0):
    values = _closes(bars)
    if length <= 0 or len(values) < length:
        return None
    w = values[-length:]
    mean = sum(w) / length
    var = sum((x - mean) ** 2 for x in w) / length
    sd = math.sqrt(var)
    return {"middle": mean, "upper": mean + mult*sd, "lower": mean - mult*sd, "width": 2*mult*sd}

def roc(bars: list[Bar], length: int = 12) -> Optional[float]:
    if length <= 0 or len(bars) <= length:
        return None
    old = bars[-length-1].close
    if old == 0:
        return None
    return ((bars[-1].close / old) - 1.0) * 100.0
