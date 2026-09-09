from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Any

@dataclass(frozen=True)
class IndicatorDefinition:
    indicator_id: str
    name: str
    family: str
    tier: str
    version: str
    enabled: bool = True
    parameters: dict[str, Any] = field(default_factory=dict)

class IndicatorRegistry:
    def __init__(self):
        self._defs: dict[str, IndicatorDefinition] = {}

    def register(self, definition: IndicatorDefinition) -> None:
        if definition.indicator_id in self._defs:
            raise ValueError(f"duplicate indicator_id: {definition.indicator_id}")
        self._defs[definition.indicator_id] = definition

    def get(self, indicator_id: str) -> IndicatorDefinition:
        return self._defs[indicator_id]

    def enabled(self) -> list[IndicatorDefinition]:
        return [d for d in self._defs.values() if d.enabled]

    def all(self) -> list[IndicatorDefinition]:
        return list(self._defs.values())

def default_registry() -> IndicatorRegistry:
    r = IndicatorRegistry()
    r.register(IndicatorDefinition("EMA_5", "Exponential Moving Average", "TREND", "A", "1.0", parameters={"length": 5}))
    r.register(IndicatorDefinition("EMA_15", "Exponential Moving Average", "TREND", "A", "1.0", parameters={"length": 15}))
    r.register(IndicatorDefinition("RSI_14", "Relative Strength Index", "MOMENTUM", "B", "1.0", parameters={"length": 14}))
    r.register(IndicatorDefinition("ATR_14", "Average True Range", "VOLATILITY", "A", "1.0", parameters={"length": 14}))
    r.register(IndicatorDefinition("BB_20_2", "Bollinger Bands", "VOLATILITY", "A", "1.0", parameters={"length": 20, "mult": 2.0}))
    return r
