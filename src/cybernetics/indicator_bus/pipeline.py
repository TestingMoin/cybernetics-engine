from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Optional
from .models import CandleInput, IndicatorSnapshot
from .state import IndicatorState

@dataclass(frozen=True)
class IndicatorDefinition:
    indicator_id: str
    version: str
    family: str
    compute: Callable[[IndicatorState,CandleInput], dict[str,float|None]]

class IndicatorPipeline:
    """
    Per-runtime deterministic indicator processing bus.

    Definitions describe calculations; state belongs to the caller/runtime.
    """
    def __init__(self):
        self._defs: dict[str,IndicatorDefinition]={}

    def register(self, definition: IndicatorDefinition) -> None:
        if definition.indicator_id in self._defs:
            raise ValueError("indicator_definition_already_registered")
        self._defs[definition.indicator_id]=definition

    def registered(self)->list[IndicatorDefinition]:
        return list(self._defs.values())

    def process(self, candle:CandleInput, state:IndicatorState)->IndicatorSnapshot:
        values={}
        ready=[]
        for definition in self._defs.values():
            result=definition.compute(state,candle)
            values.update(result)
            if all(v is not None for v in result.values()):
                ready.append(definition.indicator_id)
        return IndicatorSnapshot(
            candle.security_id,candle.timeframe,candle.timestamp,values,tuple(ready)
        )

def standard_indicator_definitions()->list[IndicatorDefinition]:
    def ema(state,c):
        # update() calculates all standard base indicators once.
        vals=state.update(c.open,c.high,c.low,c.close,c.volume)
        return {k:v for k,v in vals.items() if k.startswith("ema_")}
    def rsi(state,c):
        vals=state.update(c.open,c.high,c.low,c.close,c.volume)
        return {"rsi_14":vals["rsi_14"]}
    def atr(state,c):
        vals=state.update(c.open,c.high,c.low,c.close,c.volume)
        return {"atr_14":vals["atr_14"]}
    def bb(state,c):
        vals=state.update(c.open,c.high,c.low,c.close,c.volume)
        return {k:vals[k] for k in ("bb_mid_20","bb_upper_20_2","bb_lower_20_2")}
    def roc(state,c):
        vals=state.update(c.open,c.high,c.low,c.close,c.volume)
        return {"roc_12":vals["roc_12"]}

    # The pipeline calls definitions independently. To avoid duplicate state updates,
    # callers should normally register the consolidated definition below.
    def standard(state,c):
        return state.update(c.open,c.high,c.low,c.close,c.volume)

    return [
        IndicatorDefinition("STANDARD_BASE","1.0.0","TREND_MOMENTUM_VOLATILITY",standard)
    ]
