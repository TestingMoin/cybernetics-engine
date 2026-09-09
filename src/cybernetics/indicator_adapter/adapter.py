from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable
from cybernetics.indicators.registry import IndicatorRegistry, IndicatorSpec
from .models import RuntimeIndicatorState, IndicatorBatchResult

class IndicatorExecutionError(RuntimeError):
    pass

@dataclass(frozen=True)
class HistoryView:
    closes: tuple[float,...]
    highs: tuple[float,...]
    lows: tuple[float,...]
    volumes: tuple[float,...]

class IndicatorStateAdapter:
    """
    Bridges the versioned indicator registry to per-runtime rolling state.

    Each indicator definition receives a read-only history snapshot. The adapter
    owns the mutable runtime state and ensures one runtime cannot reuse another
    runtime's observations.
    """
    def __init__(self, registry: IndicatorRegistry, max_history: int = 500):
        if max_history <= 0:
            raise ValueError("max_history_must_be_positive")
        self.registry=registry
        self.max_history=max_history
        self._history: dict[tuple[str,str], dict[str,list[float]]] = {}

    def runtime(self, security_id: str, timeframe: str) -> RuntimeIndicatorState:
        return RuntimeIndicatorState(security_id,timeframe)

    def update_history(self, state: RuntimeIndicatorState,
                       *, high: float, low: float, close: float, volume: float) -> HistoryView:
        if min(high,low,close) < 0:
            raise ValueError("negative_market_price")
        if low > high or high < close or low > close:
            raise ValueError("invalid_ohlc")
        if volume < 0:
            raise ValueError("negative_volume")

        key=(state.security_id,state.timeframe)
        h=self._history.setdefault(key,{"closes":[],"highs":[],"lows":[],"volumes":[]})
        for name,value in (("closes",close),("highs",high),("lows",low),("volumes",volume)):
            h[name].append(value)
            if len(h[name]) > self.max_history:
                del h[name][0]

        return HistoryView(tuple(h["closes"]),tuple(h["highs"]),
                           tuple(h["lows"]),tuple(h["volumes"]))

    def process(self, state: RuntimeIndicatorState, *,
                timestamp, high: float, low: float,
                close: float, volume: float = 0.0) -> IndicatorBatchResult:
        history=self.update_history(state,high=high,low=low,close=close,volume=volume)
        values={}
        ready=[]
        for spec in self.registry.all():
            try:
                values[spec.indicator_id]=self._compute(spec,history)
            except Exception as exc:
                raise IndicatorExecutionError(
                    f"{spec.indicator_id}:{type(exc).__name__}:{exc}"
                ) from exc
            if values[spec.indicator_id] is not None:
                ready.append(spec.indicator_id)
        state.observation_count += 1
        state.last_timestamp=timestamp
        state.values.update(values)
        return IndicatorBatchResult(
            state.security_id,state.timeframe,timestamp,values,tuple(ready)
        )

    @staticmethod
    def _compute(spec: IndicatorSpec, h: HistoryView):
        # Normalize common indicator signatures without allowing hidden state.
        iid=spec.indicator_id
        if iid in {"EMA","SMA","WMA","RSI","ROC","HIGHEST","LOWEST"}:
            period={"EMA":5,"SMA":20,"WMA":20,"RSI":14,"ROC":12,"HIGHEST":20,"LOWEST":20}[iid]
            return spec.compute(h.closes,period)
        if iid=="ATR":
            return spec.compute(h.highs,h.lows,h.closes,14)
        if iid=="BB":
            return spec.compute(h.closes,20,2.0)
        if iid=="STOCH_K":
            return spec.compute(h.highs,h.lows,h.closes,14)
        if iid=="STOCH_D":
            return spec.compute(h.highs,h.lows,h.closes,14,3)
        if iid=="MACD":
            return spec.compute(h.closes,12,26,9)
        if iid=="ADX":
            return spec.compute(h.highs,h.lows,h.closes,14)
        if iid=="OBV":
            return spec.compute(h.closes,h.volumes)
        if iid=="VWAP":
            return spec.compute(h.highs,h.lows,h.closes,h.volumes)
        raise IndicatorExecutionError(f"unsupported_indicator:{iid}")
