from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Optional

class InstrumentType(str, Enum):
    EQUITY="EQUITY"
    INDEX="INDEX"
    FUTURE="FUTURE"
    OPTION="OPTION"
    COMMODITY="COMMODITY"
    CURRENCY="CURRENCY"
    UNKNOWN="UNKNOWN"

@dataclass(frozen=True)
class InstrumentIdentity:
    security_id: str
    exchange_segment: str
    symbol: str
    instrument_type: InstrumentType = InstrumentType.UNKNOWN
    underlying_security_id: Optional[str] = None
    underlying_symbol: Optional[str] = None
    expiry: Optional[str] = None
    option_type: Optional[str] = None
    strike: Optional[float] = None
    lot_size: Optional[int] = None
    tick_size: Optional[float] = None

    def __post_init__(self):
        if not self.security_id or not self.exchange_segment or not self.symbol:
            raise ValueError("instrument_identity_required")
        if self.lot_size is not None and self.lot_size <= 0:
            raise ValueError("invalid_lot_size")
        if self.tick_size is not None and self.tick_size <= 0:
            raise ValueError("invalid_tick_size")
        if self.strike is not None and self.strike < 0:
            raise ValueError("invalid_strike")

    @property
    def key(self) -> tuple[str,str]:
        return self.exchange_segment, self.security_id
