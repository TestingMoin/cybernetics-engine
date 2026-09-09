from __future__ import annotations
from dataclasses import dataclass
from typing import Literal

Status=Literal["GOLDEN","VALIDATED","RESEARCH","EXPERIMENTAL","UNSUPPORTED"]

@dataclass(frozen=True)
class ResearchAsset:
    asset_id:str
    name:str
    source_type:str
    status:Status
    notes:str=""

class ResearchRegistry:
    def __init__(self):
        self._items:dict[str,ResearchAsset]={}
    def add(self,item:ResearchAsset):
        if item.asset_id in self._items: raise ValueError(f"duplicate asset_id: {item.asset_id}")
        self._items[item.asset_id]=item
    def get(self,asset_id:str)->ResearchAsset: return self._items[asset_id]
    def all(self)->list[ResearchAsset]: return list(self._items.values())
