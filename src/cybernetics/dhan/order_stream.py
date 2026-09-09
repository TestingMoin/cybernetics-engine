from dataclasses import dataclass
from enum import Enum
from datetime import datetime
import hashlib
from cybernetics.dhan.response import DhanResponseNormalizer,DhanOrderStatus,DhanOrderResponse
from cybernetics.trading.response_binding import BrokerResponseLifecycleBinder

class StreamResult(str,Enum):
    APPLIED="APPLIED"; DUPLICATE="DUPLICATE"; STALE="STALE"; SNAPSHOT_REQUIRED="SNAPSHOT_REQUIRED"; INVALID="INVALID"

@dataclass(frozen=True)
class OrderStreamEvent:
    order:DhanOrderResponse; event_id:str; updated_at:datetime|None; raw:dict

@dataclass(frozen=True)
class OrderStreamResult:
    result:StreamResult; event:OrderStreamEvent|None; lifecycle:object|None; reason:str

class DhanOrderUpdateProcessor:
    terminal={DhanOrderStatus.TRADED,DhanOrderStatus.REJECTED,DhanOrderStatus.CANCELLED,
              DhanOrderStatus.EXPIRED,DhanOrderStatus.CLOSED}
    def __init__(self,normalizer=None,binder=None):
        self.normalizer=normalizer or DhanResponseNormalizer()
        self.binder=binder or BrokerResponseLifecycleBinder()
        self.seen=set(); self.last_ts={}; self.last_status={}
    def process(self,payload):
        try: r=self.normalizer.normalize(payload)
        except Exception as e:
            return OrderStreamResult(StreamResult.INVALID,None,None,f"invalid_order_update:{type(e).__name__}")
        eid=str(payload.get("eventId") or self._eid(r,payload))
        event=OrderStreamEvent(r,eid,self._time(payload),dict(payload))
        if eid in self.seen:
            return OrderStreamResult(StreamResult.DUPLICATE,event,None,"duplicate_event")
        ts=event.updated_at; prev=self.last_ts.get(r.order_id)
        if prev is not None and ts is None:
            return OrderStreamResult(StreamResult.SNAPSHOT_REQUIRED,event,None,"event_ordering_timestamp_missing")
        if prev is not None and ts < prev:
            return OrderStreamResult(StreamResult.STALE,event,None,"out_of_order_event")
        if self.last_status.get(r.order_id) in self.terminal and r.status != self.last_status[r.order_id]:
            return OrderStreamResult(StreamResult.SNAPSHOT_REQUIRED,event,None,"terminal_state_regression_requires_reconciliation")
        life=self.binder.bind(r)
        self.seen.add(eid); self.last_status[r.order_id]=r.status
        if ts is not None: self.last_ts[r.order_id]=ts
        return OrderStreamResult(StreamResult.APPLIED,event,life,life.reason)
    @staticmethod
    def _time(p):
        v=p.get("LastUpdatedTime")
        if not v:return None
        for f in ("%Y-%m-%d %H:%M:%S","%Y-%m-%dT%H:%M:%S","%Y-%m-%dT%H:%M:%S.%f"):
            try:return datetime.strptime(str(v),f)
            except ValueError:pass
        return None
    @staticmethod
    def _eid(r,p):
        x="|".join([r.order_id,str(r.correlation_id or ""),r.status.value,
                    str(p.get("LastUpdatedTime") or ""),str(p.get("TradedQty") or p.get("filledQty") or ""),
                    str(p.get("AvgTradedPrice") or p.get("averageTradedPrice") or "")])
        return hashlib.sha256(x.encode()).hexdigest()
    def reset(self):
        self.seen.clear(); self.last_ts.clear(); self.last_status.clear()
