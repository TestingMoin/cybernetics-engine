from __future__ import annotations
from dataclasses import dataclass, replace
from enum import Enum
from typing import Optional
import time, uuid

class OrderStatus(str, Enum):
    NEW="NEW"
    PENDING="PENDING"
    PARTIAL="PARTIAL"
    FILLED="FILLED"
    CANCEL_REQUESTED="CANCEL_REQUESTED"
    CANCELLED="CANCELLED"
    REJECTED="REJECTED"
    REPLACED="REPLACED"
    EXPIRED="EXPIRED"

@dataclass(frozen=True)
class OrderRecord:
    order_id: str
    parent_order_id: Optional[str]
    symbol: str
    side: str
    requested_quantity: int
    filled_quantity: int
    remaining_quantity: int
    order_type: str
    limit_price: Optional[float]
    stop_price: Optional[float]
    avg_fill_price: Optional[float]
    status: OrderStatus
    created_at: float
    updated_at: float
    reject_reason: Optional[str]=None

class OrderLifecycle:
    """Auditable order state machine; no broker communication."""
    ALLOWED = {
        OrderStatus.NEW:{OrderStatus.PENDING,OrderStatus.REJECTED,OrderStatus.EXPIRED},
        OrderStatus.PENDING:{OrderStatus.PARTIAL,OrderStatus.FILLED,OrderStatus.CANCEL_REQUESTED,OrderStatus.REJECTED,OrderStatus.EXPIRED},
        OrderStatus.PARTIAL:{OrderStatus.PARTIAL,OrderStatus.FILLED,OrderStatus.CANCEL_REQUESTED,OrderStatus.REJECTED,OrderStatus.EXPIRED},
        OrderStatus.CANCEL_REQUESTED:{OrderStatus.CANCELLED,OrderStatus.FILLED,OrderStatus.PARTIAL},
        OrderStatus.FILLED:set(),
        OrderStatus.CANCELLED:set(),
        OrderStatus.REJECTED:set(),
        OrderStatus.REPLACED:set(),
        OrderStatus.EXPIRED:set(),
    }

    def create(self, symbol, side, quantity, order_type, limit_price=None, stop_price=None):
        if quantity <= 0: raise ValueError("quantity must be positive")
        now=time.time()
        return OrderRecord(str(uuid.uuid4()),None,symbol,side,quantity,0,quantity,order_type,
                           limit_price,stop_price,None,OrderStatus.NEW,now,now)

    def transition(self, record:OrderRecord, status:OrderStatus, *,
                   fill_quantity:Optional[int]=None, fill_price:Optional[float]=None,
                   reject_reason:Optional[str]=None)->OrderRecord:
        if status not in self.ALLOWED[record.status]:
            raise ValueError(f"invalid transition {record.status}->{status}")
        fq=record.filled_quantity
        avg=record.avg_fill_price
        if fill_quantity is not None:
            if fill_quantity <= 0 or fq + fill_quantity > record.requested_quantity:
                raise ValueError("invalid fill quantity")
            new_fq=fq+fill_quantity
            if avg is None:
                avg=fill_price
            else:
                avg=((avg*fq)+(fill_price*fill_quantity))/new_fq
            fq=new_fq
        remaining=record.requested_quantity-fq
        if status==OrderStatus.PARTIAL and remaining<=0: status=OrderStatus.FILLED
        if status==OrderStatus.FILLED and remaining!=0: raise ValueError("filled order must have zero remaining")
        return replace(record,status=status,filled_quantity=fq,remaining_quantity=remaining,
                       avg_fill_price=avg,updated_at=time.time(),reject_reason=reject_reason)

    def replace(self, record:OrderRecord, *, quantity:Optional[int]=None, limit_price=...):
        if record.status not in {OrderStatus.PENDING,OrderStatus.PARTIAL}:
            raise ValueError("only working orders can be replaced")
        q=record.remaining_quantity if quantity is None else quantity
        if q <= 0: raise ValueError("replacement quantity must be positive")
        lp=record.limit_price if limit_price is ... else limit_price
        now=time.time()
        return OrderRecord(str(uuid.uuid4()),record.order_id,record.symbol,record.side,
                           q,0,q,record.order_type,lp,record.stop_price,None,
                           OrderStatus.NEW,now,now)

    def event(self, record:OrderRecord)->dict:
        return {
            "order_id":record.order_id,"parent_order_id":record.parent_order_id,
            "symbol":record.symbol,"side":record.side,
            "requested_quantity":record.requested_quantity,
            "filled_quantity":record.filled_quantity,
            "remaining_quantity":record.remaining_quantity,
            "status":record.status.value,"avg_fill_price":record.avg_fill_price,
            "created_at":record.created_at,"updated_at":record.updated_at,
            "reject_reason":record.reject_reason,
        }
