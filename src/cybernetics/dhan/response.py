from dataclasses import dataclass
from enum import Enum

class DhanOrderStatus(str, Enum):
    TRANSIT="TRANSIT"; PENDING="PENDING"; PART_TRADED="PART_TRADED"; TRADED="TRADED"
    REJECTED="REJECTED"; CANCELLED="CANCELLED"; EXPIRED="EXPIRED"; CLOSED="CLOSED"
    TRIGGERED="TRIGGERED"; UNKNOWN="UNKNOWN"

@dataclass(frozen=True)
class DhanOrderResponse:
    order_id:str; correlation_id:str|None; status:DhanOrderStatus
    filled_quantity:int=0; remaining_quantity:int|None=None
    average_traded_price:float|None=None; raw:dict|None=None

class DhanResponseNormalizer:
    def normalize(self,payload):
        if not payload.get("orderId"): raise ValueError("dhan_response_order_id_required")
        st=DhanOrderStatus.__members__.get(str(payload.get("orderStatus","UNKNOWN")).upper(),
                                            DhanOrderStatus.UNKNOWN)
        fq=payload.get("filledQty",payload.get("TradedQty",0))
        rq=payload.get("remainingQuantity")
        ap=payload.get("averageTradedPrice",payload.get("AvgTradedPrice"))
        return DhanOrderResponse(str(payload["orderId"]),
            None if payload.get("correlationId") is None else str(payload["correlationId"]),
            st,int(fq or 0),None if rq is None else int(rq),
            None if ap in (None,"") else float(ap),dict(payload))
