from dataclasses import dataclass
from enum import Enum
from cybernetics.dhan.response import DhanOrderStatus

class LedgerOrderState(str,Enum):
    PENDING="PENDING"; PARTIAL="PARTIAL"; FILLED="FILLED"; REJECTED="REJECTED"
    CANCELLED="CANCELLED"; EXPIRED="EXPIRED"; UNKNOWN="UNKNOWN"

@dataclass(frozen=True)
class NormalizedOrderEvent:
    order_id:str; correlation_id:str|None; state:LedgerOrderState
    filled_quantity:int; remaining_quantity:int|None
    average_traded_price:float|None; terminal:bool; reason:str

class BrokerResponseLifecycleBinder:
    def bind(self,r):
        m={
          DhanOrderStatus.TRANSIT:(LedgerOrderState.PENDING,False,"broker_transit"),
          DhanOrderStatus.PENDING:(LedgerOrderState.PENDING,False,"broker_pending"),
          DhanOrderStatus.PART_TRADED:(LedgerOrderState.PARTIAL,False,"broker_partial_fill"),
          DhanOrderStatus.TRADED:(LedgerOrderState.FILLED,True,"broker_filled"),
          DhanOrderStatus.REJECTED:(LedgerOrderState.REJECTED,True,"broker_rejected"),
          DhanOrderStatus.CANCELLED:(LedgerOrderState.CANCELLED,True,"broker_cancelled"),
          DhanOrderStatus.EXPIRED:(LedgerOrderState.EXPIRED,True,"broker_expired"),
          DhanOrderStatus.CLOSED:(LedgerOrderState.FILLED,True,"broker_closed"),
          DhanOrderStatus.TRIGGERED:(LedgerOrderState.PENDING,False,"broker_triggered"),
          DhanOrderStatus.UNKNOWN:(LedgerOrderState.UNKNOWN,False,"broker_status_unknown"),
        }
        if r.filled_quantity<0: raise ValueError("filled_quantity_invalid")
        s,t,reason=m[r.status]
        return NormalizedOrderEvent(r.order_id,r.correlation_id,s,r.filled_quantity,
            r.remaining_quantity,r.average_traded_price,t,reason)
