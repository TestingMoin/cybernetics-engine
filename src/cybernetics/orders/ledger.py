from __future__ import annotations
from dataclasses import dataclass
from .lifecycle import OrderRecord

@dataclass(frozen=True)
class OrderEvent:
    seq:int
    order_id:str
    event_type:str
    status:str
    timestamp:float
    details:dict

class OrderLedger:
    """Append-only in-memory audit ledger; persistent DB comes later."""
    def __init__(self):
        self._seq=0
        self.events:list[OrderEvent]=[]

    def append(self, order:OrderRecord, event_type:str, timestamp:float, **details):
        self._seq+=1
        self.events.append(OrderEvent(self._seq,order.order_id,event_type,order.status.value,timestamp,details))

    def for_order(self, order_id:str):
        return [e for e in self.events if e.order_id==order_id]
