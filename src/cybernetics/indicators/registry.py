from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Any

class IndicatorTier(str, Enum):
    CORE="CORE"
    ADVANCED="ADVANCED"
    RESEARCH="RESEARCH"

@dataclass(frozen=True)
class IndicatorSpec:
    indicator_id: str
    version: str
    family: str
    tier: IndicatorTier
    compute: Callable[..., Any]
    description: str = ""

class IndicatorRegistry:
    def __init__(self):
        self._items: dict[str, IndicatorSpec]={}

    def register(self,spec:IndicatorSpec)->None:
        if not spec.indicator_id or not spec.version:
            raise ValueError("indicator_identity_required")
        if spec.indicator_id in self._items:
            raise ValueError("indicator_already_registered")
        self._items[spec.indicator_id]=spec

    def get(self,indicator_id:str)->IndicatorSpec:
        try:
            return self._items[indicator_id]
        except KeyError:
            raise KeyError("indicator_not_found")

    def all(self)->list[IndicatorSpec]:
        return list(self._items.values())

    def by_family(self,family:str)->list[IndicatorSpec]:
        return [x for x in self._items.values() if x.family==family]

    def by_tier(self,tier:IndicatorTier)->list[IndicatorSpec]:
        return [x for x in self._items.values() if x.tier==tier]
