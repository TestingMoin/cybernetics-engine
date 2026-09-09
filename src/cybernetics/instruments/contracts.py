from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from typing import Iterable, Optional
from .identity import InstrumentIdentity, InstrumentType
from .master import InstrumentMaster

@dataclass(frozen=True)
class ContractSelection:
    requested_underlying: str
    instrument_type: InstrumentType
    expiry: Optional[str]
    instrument: InstrumentIdentity

class ContractResolver:
    """
    Resolves option/future contracts from the instrument master.

    Selection is data-driven and never manufactures a symbol/security ID.
    """
    def __init__(self, master:InstrumentMaster):
        self.master=master

    def futures(self, underlying_symbol:str, expiry:Optional[str]=None)->list[ContractSelection]:
        rows=[
            x for x in self.master.all()
            if x.instrument_type==InstrumentType.FUTURE
            and (x.underlying_symbol==underlying_symbol or x.symbol.startswith(underlying_symbol))
            and self.master.trade_eligible(x.key)
        ]
        rows.sort(key=lambda x:(x.expiry or "",x.security_id))
        if expiry is not None:
            rows=[x for x in rows if x.expiry==expiry]
        return [ContractSelection(underlying_symbol,InstrumentType.FUTURE,x.expiry,x) for x in rows]

    def options(self, underlying_symbol:str, expiry:Optional[str]=None,
                strike:Optional[float]=None, option_type:Optional[str]=None)->list[ContractSelection]:
        rows=[
            x for x in self.master.all()
            if x.instrument_type==InstrumentType.OPTION
            and x.underlying_symbol==underlying_symbol
            and self.master.trade_eligible(x.key)
        ]
        if expiry is not None: rows=[x for x in rows if x.expiry==expiry]
        if strike is not None: rows=[x for x in rows if x.strike==strike]
        if option_type is not None: rows=[x for x in rows if x.option_type==option_type]
        rows.sort(key=lambda x:(x.expiry or "",x.strike if x.strike is not None else -1,x.option_type or "",x.security_id))
        return [ContractSelection(underlying_symbol,InstrumentType.OPTION,x.expiry,x) for x in rows]

    def nearest_expiry(self, contracts:Iterable[ContractSelection], on_date:date)->Optional[ContractSelection]:
        eligible=[]
        for c in contracts:
            if not c.expiry: continue
            try:
                d=date.fromisoformat(c.expiry)
            except ValueError:
                continue
            if d>=on_date: eligible.append((d,c))
        if not eligible: return None
        return min(eligible,key=lambda x:(x[0],x[1].instrument.security_id))[1]
