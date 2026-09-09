from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Optional
from .identity import InstrumentIdentity, InstrumentType

class InstrumentLifecycle(str, Enum):
    UNVERIFIED="UNVERIFIED"
    ACTIVE="ACTIVE"
    WARNING="WARNING"
    NO_NEW_TRADES="NO_NEW_TRADES"
    RETIRED="RETIRED"

@dataclass(frozen=True)
class UniverseChange:
    added: tuple[InstrumentIdentity,...]
    changed: tuple[InstrumentIdentity,...]
    removed: tuple[InstrumentIdentity,...]

class InstrumentMaster:
    """
    Runtime instrument registry.

    The master is source-driven: rows are loaded from an external instrument-master
    feed and converted into InstrumentIdentity. No trading universe is hardcoded here.
    """
    def __init__(self):
        self._items: dict[tuple[str,str],InstrumentIdentity]={}
        self._lifecycle: dict[tuple[str,str],InstrumentLifecycle]={}
        self._generation=0

    @property
    def generation(self)->int:
        return self._generation

    def load(self, rows: Iterable[dict]) -> UniverseChange:
        incoming={}
        for row in rows:
            item=self.from_row(row)
            if item.key in incoming:
                raise ValueError(f"duplicate_instrument_key:{item.key}")
            incoming[item.key]=item

        old_keys=set(self._items)
        new_keys=set(incoming)
        added=sorted(new_keys-old_keys)
        removed=sorted(old_keys-new_keys)
        changed=sorted(k for k in old_keys & new_keys if self._items[k]!=incoming[k])

        for k in added:
            self._lifecycle[k]=InstrumentLifecycle.UNVERIFIED
        for k in removed:
            previous=self._lifecycle.get(k,InstrumentLifecycle.ACTIVE)
            if previous != InstrumentLifecycle.RETIRED:
                self._lifecycle[k]=InstrumentLifecycle.WARNING
        self._items=incoming
        self._generation+=1
        return UniverseChange(
            tuple(incoming[k] for k in added),
            tuple(incoming[k] for k in changed),
            tuple(self._items[k] for k in changed),
        ) if False else UniverseChange(
            tuple(incoming[k] for k in added),
            tuple(incoming[k] for k in changed),
            tuple(self._retired_snapshot(k) for k in removed),
        )

    def approve(self, key:tuple[str,str]) -> None:
        self._require(key)
        if self._lifecycle.get(key) in {InstrumentLifecycle.UNVERIFIED, InstrumentLifecycle.WARNING}:
            self._lifecycle[key]=InstrumentLifecycle.ACTIVE

    def warn(self,key): self._lifecycle[key]=InstrumentLifecycle.WARNING
    def block_new_trades(self,key): self._lifecycle[key]=InstrumentLifecycle.NO_NEW_TRADES
    def retire(self,key):
        self._require_or_lifecycle(key)
        self._lifecycle[key]=InstrumentLifecycle.RETIRED

    def lifecycle(self,key):
        return self._lifecycle.get(key,InstrumentLifecycle.RETIRED)

    def get(self,key)->Optional[InstrumentIdentity]:
        return self._items.get(key)

    def all(self)->list[InstrumentIdentity]:
        return list(self._items.values())

    def trade_eligible(self,key)->bool:
        return self.lifecycle(key)==InstrumentLifecycle.ACTIVE

    def _retired_snapshot(self,key):
        item=self._items.get(key)
        if item is not None: return item
        return InstrumentIdentity(
            security_id=key[1],exchange_segment=key[0],symbol="RETIRED",
            instrument_type=InstrumentType.UNKNOWN
        )

    def _require(self,key):
        if key not in self._items:
            raise KeyError("instrument_not_found")

    def _require_or_lifecycle(self,key):
        if key not in self._items and key not in self._lifecycle:
            raise KeyError("instrument_not_found")

    @staticmethod
    def from_row(row:dict)->InstrumentIdentity:
        if not isinstance(row,dict):
            raise ValueError("instrument_row_must_be_dict")
        instrument=str(row.get("INSTRUMENT") or row.get("instrument") or "").upper()
        itype=InstrumentType.UNKNOWN
        if "OPT" in instrument: itype=InstrumentType.OPTION
        elif "FUT" in instrument: itype=InstrumentType.FUTURE
        elif instrument in {"EQUITY","EQ"}: itype=InstrumentType.EQUITY
        elif instrument in {"INDEX","IDX"}: itype=InstrumentType.INDEX
        elif "CUR" in instrument: itype=InstrumentType.CURRENCY
        elif "COM" in instrument: itype=InstrumentType.COMMODITY

        return InstrumentIdentity(
            security_id=str(row.get("SECURITY_ID") or row.get("SecurityId") or ""),
            exchange_segment=str(row.get("EXCHANGE_SEGMENT") or row.get("ExchangeSegment") or ""),
            symbol=str(row.get("TRADING_SYMBOL") or row.get("SEM_TRADING_SYMBOL") or row.get("SYMBOL_NAME") or ""),
            instrument_type=itype,
            underlying_security_id=(str(row["UNDERLYING_SECURITY_ID"]) if row.get("UNDERLYING_SECURITY_ID") is not None else None),
            underlying_symbol=(str(row["UNDERLYING_SYMBOL"]) if row.get("UNDERLYING_SYMBOL") is not None else None),
            expiry=(str(row["EXPIRY"]) if row.get("EXPIRY") is not None else None),
            option_type=(str(row["OPTION_TYPE"]) if row.get("OPTION_TYPE") is not None else None),
            strike=(float(row["STRIKE"]) if row.get("STRIKE") is not None else None),
            lot_size=(int(row["LOT_SIZE"]) if row.get("LOT_SIZE") is not None else None),
            tick_size=(float(row["TICK_SIZE"]) if row.get("TICK_SIZE") is not None else None),
        )
