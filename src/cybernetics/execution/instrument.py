from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from datetime import date
from typing import Optional


class InstrumentType(str, Enum):
    EQUITY = "EQUITY"
    INDEX = "INDEX"
    FUTURE = "FUTURE"
    OPTION = "OPTION"
    COMMODITY = "COMMODITY"


class OptionType(str, Enum):
    CE = "CE"
    PE = "PE"


@dataclass(frozen=True)
class InstrumentEligibility:
    validated: bool
    approved: bool
    active: bool
    production_eligible: bool
    reason: str = ""


@dataclass(frozen=True)
class TradeInstrument:
    exchange_segment: str
    security_id: str
    symbol: str
    instrument_type: InstrumentType
    expiry: Optional[date] = None
    strike: Optional[float] = None
    option_type: Optional[OptionType] = None
    lot_size: int = 1
    tick_size: float = 0.05
    contract_multiplier: float = 1.0
    eligibility: Optional[InstrumentEligibility] = None

    def __post_init__(self):
        if not self.exchange_segment or not self.security_id or not self.symbol:
            raise ValueError("instrument_identity_required")
        if self.lot_size <= 0:
            raise ValueError("lot_size_must_be_positive")
        if self.tick_size <= 0:
            raise ValueError("tick_size_must_be_positive")
        if self.contract_multiplier <= 0:
            raise ValueError("contract_multiplier_must_be_positive")

        if self.instrument_type == InstrumentType.OPTION:
            if self.expiry is None:
                raise ValueError("option_expiry_required")
            if self.strike is None or self.strike <= 0:
                raise ValueError("option_strike_required")
            if self.option_type is None:
                raise ValueError("option_type_required")


@dataclass(frozen=True)
class InstrumentSelectionRequest:
    exchange_segment: str
    underlying_key: str
    instrument_type: InstrumentType
    expiry: Optional[date] = None
    strike: Optional[float] = None
    option_type: Optional[OptionType] = None
    lot_size: Optional[int] = None
    require_production_eligible: bool = True


class InstrumentSelector:
    """
    Deterministic selection boundary.

    The upstream Universe / Contract Resolver is expected to provide the exact
    candidate set. This class only selects among supplied candidates and never
    invents a security ID or contract.
    """

    def select(
        self,
        request: InstrumentSelectionRequest,
        candidates: list[TradeInstrument],
    ) -> TradeInstrument:
        matching = []
        for item in candidates:
            if item.exchange_segment != request.exchange_segment:
                continue
            if item.instrument_type != request.instrument_type:
                continue

            # Symbol/underlying identity is represented by the candidate symbol.
            # The resolver upstream is responsible for mapping aliases.
            if item.symbol != request.underlying_key:
                continue

            if request.expiry is not None and item.expiry != request.expiry:
                continue
            if request.strike is not None and item.strike != request.strike:
                continue
            if request.option_type is not None and item.option_type != request.option_type:
                continue
            if request.lot_size is not None and item.lot_size != request.lot_size:
                continue

            if request.require_production_eligible:
                e = item.eligibility
                if e is None or not (
                    e.validated and e.approved and e.active and e.production_eligible
                ):
                    continue

            matching.append(item)

        if not matching:
            raise LookupError("no_production_eligible_instrument_match")

        if len(matching) > 1:
            raise LookupError("ambiguous_instrument_selection")

        return matching[0]
