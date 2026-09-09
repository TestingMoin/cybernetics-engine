from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Optional

class PositionReconciliationStatus(str,Enum):
    CONSISTENT="CONSISTENT"
    MISMATCH="MISMATCH"
    BROKER_ONLY="BROKER_ONLY"
    INTERNAL_ONLY="INTERNAL_ONLY"
    INVALID="INVALID"

@dataclass(frozen=True)
class BrokerPosition:
    exchange_segment:str
    security_id:str
    trading_symbol:str
    position_type:str
    net_qty:int
    average_price:Optional[float]
    realized_profit:Optional[float]=None
    unrealized_profit:Optional[float]=None

@dataclass(frozen=True)
class PositionReconciliation:
    key:str
    status:PositionReconciliationStatus
    quantity_match:bool
    side_match:bool
    average_price_match:bool
    reason:str
    internal_quantity:int=0
    broker_quantity:int=0
    internal_average:Optional[float]=None
    broker_average:Optional[float]=None

@dataclass(frozen=True)
class InternalPosition:
    exchange_segment:str
    security_id:str
    trading_symbol:str
    side:str
    quantity:int
    average_entry_price:Optional[float]

class PositionReconciler:
    """
    Compares internal position truth with broker position truth.

    Dhan's GET /positions response exposes netQty, positionType and costPrice;
    these are used as the canonical broker-side quantity/side/cost basis.
    buyAvg/sellAvg and P&L fields are retained by the caller if needed for
    separate valuation audits.
    """
    def __init__(self, price_tolerance:float=1e-6):
        if price_tolerance < 0:
            raise ValueError("price_tolerance_must_be_non_negative")
        self.price_tolerance=price_tolerance

    def reconcile(
        self,
        internal:Optional[InternalPosition],
        broker:Optional[BrokerPosition],
    ) -> PositionReconciliation:
        if internal is None and broker is None:
            return PositionReconciliation("UNKNOWN",PositionReconciliationStatus.INVALID,
                False,False,False,"both_positions_missing")
        key=(internal.security_id if internal else broker.security_id)
        if internal is None:
            return PositionReconciliation(key,PositionReconciliationStatus.BROKER_ONLY,
                False,False,False,"broker_position_not_present_in_internal_state",
                0,abs(broker.net_qty),None,broker.average_price)
        if broker is None:
            return PositionReconciliation(internal.security_id,PositionReconciliationStatus.INTERNAL_ONLY,
                False,False,False,"internal_position_not_present_at_broker",
                internal.quantity,0,internal.average_entry_price,None)

        if internal.exchange_segment != broker.exchange_segment or internal.security_id != broker.security_id:
            return PositionReconciliation(
                internal.security_id,PositionReconciliationStatus.MISMATCH,
                False,False,False,"position_identity_mismatch",
                internal.quantity,abs(broker.net_qty),internal.average_entry_price,broker.average_price)

        bqty=abs(broker.net_qty)
        qmatch=internal.quantity==bqty
        is_b_long=broker.net_qty>0 or broker.position_type.upper()=="LONG"
        is_b_short=broker.net_qty<0 or broker.position_type.upper()=="SHORT"
        smatch=((internal.side.upper()=="LONG" and is_b_long) or
                (internal.side.upper()=="SHORT" and is_b_short) or
                (internal.side.upper()=="FLAT" and bqty==0))

        if internal.average_entry_price is None or broker.average_price is None:
            pmatch=internal.average_entry_price is None and broker.average_price is None
        else:
            pmatch=abs(internal.average_entry_price-broker.average_price)<=self.price_tolerance

        ok=qmatch and smatch and pmatch
        return PositionReconciliation(
            internal.security_id,
            PositionReconciliationStatus.CONSISTENT if ok else PositionReconciliationStatus.MISMATCH,
            qmatch,smatch,pmatch,
            "positions_consistent" if ok else "position_state_mismatch",
            internal.quantity,bqty,internal.average_entry_price,broker.average_price)

class ReconciliationTradingGate:
    """
    Converts reconciliation result into a conservative trading permission.

    Consistency allows new entries. Any other state blocks new entries until a
    dedicated recovery/reconciliation workflow resolves the discrepancy.
    """
    def can_open_new_trade(self,result:PositionReconciliation)->bool:
        return result.status==PositionReconciliationStatus.CONSISTENT
