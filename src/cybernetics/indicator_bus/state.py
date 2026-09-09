from __future__ import annotations
from collections import deque
from dataclasses import dataclass
from math import sqrt
from typing import Optional

@dataclass
class IndicatorState:
    """
    Deterministic per-runtime indicator state.

    This state object is deliberately reusable but must be instantiated once
    per scanner runtime + timeframe. It never stores cross-instrument state.
    """
    ema_periods: tuple[int, ...] = (5, 15)
    rsi_period: int = 14
    atr_period: int = 14
    bb_period: int = 20
    bb_mult: float = 2.0
    roc_period: int = 12

    closes: deque = None
    highs: deque = None
    lows: deque = None
    prev_close: Optional[float] = None
    ema: dict[int, Optional[float]] = None
    gain_sum: float = 0.0
    loss_sum: float = 0.0
    rsi_count: int = 0
    tr_values: deque = None
    roc_history: deque = None

    def __post_init__(self):
        self.closes=deque(maxlen=max(self.bb_period,self.roc_period)+1)
        self.highs=deque(maxlen=self.atr_period+1)
        self.lows=deque(maxlen=self.atr_period+1)
        self.tr_values=deque(maxlen=self.atr_period)
        self.roc_history=deque(maxlen=self.roc_period+1)
        self.ema={p:None for p in self.ema_periods}
        if self.rsi_period <= 0 or self.atr_period <= 0 or self.bb_period <= 1 or self.roc_period <= 0:
            raise ValueError("invalid_indicator_period")

    def update(self, open_: float, high: float, low: float, close: float,
               volume: float = 0.0) -> dict[str, float | None]:
        if low > high:
            raise ValueError("low_above_high")
        self.closes.append(close)
        self.highs.append(high)
        self.lows.append(low)

        for p in self.ema_periods:
            alpha=2/(p+1)
            prev=self.ema[p]
            if prev is None:
                if len(self.closes) >= p:
                    # SMA seed from last p closes.
                    self.ema[p]=sum(list(self.closes)[-p:])/p
            else:
                self.ema[p]=alpha*close+(1-alpha)*prev

        rsi=self._rsi(close)
        atr=self._atr(high,low,close)
        bb_mid=bb_upper=bb_lower=None
        if len(self.closes) >= self.bb_period:
            xs=list(self.closes)[-self.bb_period:]
            mean=sum(xs)/self.bb_period
            var=sum((x-mean)**2 for x in xs)/self.bb_period
            sd=sqrt(var)
            bb_mid=mean
            bb_upper=mean+self.bb_mult*sd
            bb_lower=mean-self.bb_mult*sd

        roc=None
        self.roc_history.append(close)
        if len(self.roc_history) > self.roc_period:
            base=self.roc_history[-self.roc_period-1]
            if base != 0:
                roc=(close/base-1.0)*100

        self.prev_close=close
        out={}
        for p in self.ema_periods:
            out[f"ema_{p}"]=self.ema[p]
        out["rsi_14"]=rsi
        out["atr_14"]=atr
        out["bb_mid_20"]=bb_mid
        out["bb_upper_20_2"]=bb_upper
        out["bb_lower_20_2"]=bb_lower
        out["roc_12"]=roc
        out["close"]=close
        out["volume"]=volume
        return out

    def _rsi(self, close):
        if self.prev_close is None:
            return None
        change=close-self.prev_close
        gain=max(change,0.0)
        loss=max(-change,0.0)
        self.rsi_count += 1
        if self.rsi_count <= self.rsi_period:
            self.gain_sum += gain
            self.loss_sum += loss
            if self.rsi_count < self.rsi_period:
                return None
            avg_gain=self.gain_sum/self.rsi_period
            avg_loss=self.loss_sum/self.rsi_period
        else:
            # Wilder smoothing.
            prior_gain=getattr(self,"_avg_gain",self.gain_sum/self.rsi_period)
            prior_loss=getattr(self,"_avg_loss",self.loss_sum/self.rsi_period)
            avg_gain=(prior_gain*(self.rsi_period-1)+gain)/self.rsi_period
            avg_loss=(prior_loss*(self.rsi_period-1)+loss)/self.rsi_period
        self._avg_gain=avg_gain
        self._avg_loss=avg_loss
        if avg_loss == 0:
            return 100.0 if avg_gain > 0 else 50.0
        rs=avg_gain/avg_loss
        return 100-100/(1+rs)

    def _atr(self, high, low, close):
        if self.prev_close is None:
            tr=high-low
        else:
            tr=max(high-low,abs(high-self.prev_close),abs(low-self.prev_close))
        self.tr_values.append(tr)
        if len(self.tr_values) < self.atr_period:
            return None
        if not hasattr(self,"_atr_value"):
            self._atr_value=sum(self.tr_values)/self.atr_period
        else:
            self._atr_value=(self._atr_value*(self.atr_period-1)+tr)/self.atr_period
        return self._atr_value
