
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from math import floor, isfinite
from typing import Optional

class SizingDecision(str, Enum):
    APPROVED="APPROVED"
    REJECTED="REJECTED"

@dataclass(frozen=True)
class SizingRequest:
    # Current contract fields
    entry_price: float
    stop_price: float
    risk_budget: float
    lot_size: int
    contract_multiplier: float=1.0
    max_quantity: Optional[int]=None
    max_notional: Optional[float]=None
    available_margin: Optional[float]=None
    margin_per_unit: Optional[float]=None
    # Legacy stop-risk fields, retained for compatibility with Chunk 14.
    capital: Optional[float]=None
    risk_fraction: Optional[float]=None
    price: Optional[float]=None
    margin_per_lot: Optional[float]=None
    max_lots: Optional[int]=None

    def __init__(self, *args, **kwargs):
        if args and len(args)==8 and not kwargs:
            capital,risk_fraction,price,stop_price,lot_size,available_margin,margin_per_lot,max_lots=args
            object.__setattr__(self,"entry_price",float(price))
            object.__setattr__(self,"stop_price",float(stop_price))
            object.__setattr__(self,"risk_budget",float(capital)*float(risk_fraction))
            object.__setattr__(self,"lot_size",int(lot_size))
            object.__setattr__(self,"contract_multiplier",1.0)
            object.__setattr__(self,"max_quantity",int(lot_size)*int(max_lots))
            object.__setattr__(self,"max_notional",None)
            object.__setattr__(self,"available_margin",float(available_margin))
            object.__setattr__(self,"margin_per_unit",float(margin_per_lot)/int(lot_size))
            object.__setattr__(self,"capital",float(capital))
            object.__setattr__(self,"risk_fraction",float(risk_fraction))
            object.__setattr__(self,"price",float(price))
            object.__setattr__(self,"margin_per_lot",float(margin_per_lot))
            object.__setattr__(self,"max_lots",int(max_lots))
            return
        fields=("entry_price","stop_price","risk_budget","lot_size","contract_multiplier",
                "max_quantity","max_notional","available_margin","margin_per_unit",
                "capital","risk_fraction","price","margin_per_lot","max_lots")
        if args:
            if len(args)>9: raise TypeError("too_many_positional_arguments")
            for k,v in zip(fields,args): kwargs.setdefault(k,v)
        defaults={"contract_multiplier":1.0,"max_quantity":None,"max_notional":None,
                  "available_margin":None,"margin_per_unit":None,
                  "capital":None,"risk_fraction":None,"price":None,
                  "margin_per_lot":None,"max_lots":None}
        for k,v in defaults.items(): kwargs.setdefault(k,v)
        required=("entry_price","stop_price","risk_budget","lot_size")
        for k in required:
            if k not in kwargs: raise TypeError(f"missing_required_field:{k}")
        for k in fields: object.__setattr__(self,k,kwargs[k])
        if not isfinite(self.entry_price) or self.entry_price<=0: raise ValueError("entry_price_must_be_positive")
        if not isfinite(self.stop_price) or self.stop_price<=0: raise ValueError("stop_price_must_be_positive")
        if not isfinite(self.risk_budget) or self.risk_budget<=0: raise ValueError("risk_budget_must_be_positive")
        if self.lot_size<=0: raise ValueError("lot_size_must_be_positive")

@dataclass(frozen=True)
class SizingResult:
    decision: SizingDecision
    reason: str
    quantity: int = 0
    lots: int = 0
    risk_per_unit: float = 0.0
    trade_risk: float = 0.0
    notional: float = 0.0
    estimated_margin: float = 0.0

def size_by_stop_risk(req):
    import math
    if min(req.capital, req.price, req.stop_price, req.margin_per_lot) <= 0:
        return 0
    if req.lot_size <= 0 or req.max_lots <= 0:
        return 0
    if not 0 < req.risk_fraction <= 1:
        return 0
    per_unit_risk=abs(req.price-req.stop_price)
    if per_unit_risk<=0:
        return 0
    risk_budget=req.capital*req.risk_fraction
    lots_by_risk=math.floor(risk_budget/(per_unit_risk*req.lot_size))
    lots_by_margin=math.floor(req.available_margin/req.margin_per_lot)
    lots=max(0,min(lots_by_risk,lots_by_margin,req.max_lots))
    return lots*req.lot_size


class PositionSizingEngine:
    """
    Deterministic risk-based position sizing.

    Formula:
      risk_per_unit = abs(entry - stop) * contract_multiplier
      raw_quantity = floor(risk_budget / risk_per_unit)
      quantity = floor(raw_quantity / lot_size) * lot_size

    Quantity is never forced to one lot. If the calculated risk cannot support
    a full lot, the result is rejected.
    """

    def size(self, request: SizingRequest) -> SizingResult:
        stop_distance = abs(request.entry_price - request.stop_price)

        if stop_distance <= 0:
            return SizingResult(
                SizingDecision.REJECTED, "entry_and_stop_must_differ"
            )

        risk_per_unit = stop_distance * request.contract_multiplier
        if risk_per_unit <= 0 or not isfinite(risk_per_unit):
            return SizingResult(
                SizingDecision.REJECTED, "risk_per_unit_invalid"
            )

        raw_quantity = floor(request.risk_budget / risk_per_unit)

        if raw_quantity < request.lot_size:
            return SizingResult(
                SizingDecision.REJECTED,
                "risk_budget_below_one_full_lot_risk",
                risk_per_unit=risk_per_unit,
            )

        quantity = (raw_quantity // request.lot_size) * request.lot_size

        if request.max_quantity is not None:
            quantity = min(quantity, (request.max_quantity // request.lot_size) * request.lot_size)

        if quantity <= 0:
            return SizingResult(
                SizingDecision.REJECTED,
                "lot_aligned_quantity_zero",
                risk_per_unit=risk_per_unit,
            )

        notional = quantity * request.entry_price * request.contract_multiplier
        trade_risk = quantity * risk_per_unit

        if request.max_notional is not None and notional > request.max_notional:
            capped = floor(request.max_notional / (request.entry_price * request.contract_multiplier))
            capped = (capped // request.lot_size) * request.lot_size
            if capped <= 0:
                return SizingResult(
                    SizingDecision.REJECTED,
                    "max_notional_below_one_full_lot",
                    risk_per_unit=risk_per_unit,
                )
            quantity = min(quantity, capped)
            if quantity <= 0:
                return SizingResult(
                    SizingDecision.REJECTED,
                    "notional_cap_produces_zero_quantity",
                    risk_per_unit=risk_per_unit,
                )
            notional = quantity * request.entry_price * request.contract_multiplier
            trade_risk = quantity * risk_per_unit

        estimated_margin = 0.0
        if request.margin_per_unit is not None:
            estimated_margin = quantity * request.margin_per_unit
            if request.available_margin is not None and estimated_margin > request.available_margin:
                capped = floor(request.available_margin / request.margin_per_unit)
                capped = (capped // request.lot_size) * request.lot_size
                if capped <= 0:
                    return SizingResult(
                        SizingDecision.REJECTED,
                        "available_margin_below_one_full_lot",
                        risk_per_unit=risk_per_unit,
                    )
                quantity = min(quantity, capped)
                notional = quantity * request.entry_price * request.contract_multiplier
                trade_risk = quantity * risk_per_unit
                estimated_margin = quantity * request.margin_per_unit

        lots = quantity // request.lot_size

        return SizingResult(
            SizingDecision.APPROVED,
            "risk_sized_quantity_created",
            quantity=quantity,
            lots=lots,
            risk_per_unit=risk_per_unit,
            trade_risk=trade_risk,
            notional=notional,
            estimated_margin=estimated_margin,
        )
