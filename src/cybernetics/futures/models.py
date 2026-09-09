from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Optional


@dataclass(frozen=True)
class ContractSpec:
    security_id: str
    exchange: str
    segment: str
    underlying_symbol: str
    trading_symbol: str
    expiry: date
    lot_size: int
    tick_size: Decimal
    multiplier: Decimal = Decimal("1")
    currency: str = "INR"
    active: bool = True

    def __post_init__(self) -> None:
        if not self.security_id:
            raise ValueError("security_id is required")
        if self.lot_size <= 0:
            raise ValueError("lot_size must be positive")
        if self.tick_size <= 0:
            raise ValueError("tick_size must be positive")
        if self.multiplier <= 0:
            raise ValueError("multiplier must be positive")


@dataclass(frozen=True)
class FuturesQuote:
    security_id: str
    timestamp: datetime
    ltp: Decimal
    bid: Optional[Decimal] = None
    ask: Optional[Decimal] = None
    volume: Optional[int] = None
    open_interest: Optional[int] = None
    previous_close: Optional[Decimal] = None


@dataclass
class FuturesState:
    contract: ContractSpec
    last_quote: Optional[FuturesQuote] = None
    previous_oi: Optional[int] = None
    previous_volume: Optional[int] = None
    previous_ltp: Optional[Decimal] = None
    realized_mtm: Decimal = Decimal("0")
    oi_change: Optional[int] = None
    volume_change: Optional[int] = None
    basis: Optional[Decimal] = None
    rejected_quotes: int = 0
    metadata: dict = field(default_factory=dict)
