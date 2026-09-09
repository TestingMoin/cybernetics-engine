from dataclasses import dataclass
from enum import Enum
from typing import Optional

class PositionSide(str,Enum):
    FLAT="FLAT"; LONG="LONG"; SHORT="SHORT"

@dataclass(frozen=True)
class FillEvent:
    fill_id:str
    order_id:str
    trade_id:str
    underlying_key:str
    side:str
    quantity:int
    price:float
    fee:float=0.0
    def __post_init__(self):
        if not self.fill_id or not self.order_id or not self.trade_id or not self.underlying_key:
            raise ValueError("fill_identity_required")
        if self.side.upper() not in {"BUY","SELL"}: raise ValueError("unsupported_fill_side")
        if self.quantity<=0: raise ValueError("fill_quantity_must_be_positive")
        if self.price<=0: raise ValueError("fill_price_must_be_positive")
        if self.fee<0: raise ValueError("fill_fee_must_be_non_negative")

@dataclass(frozen=True)
class PositionSnapshot:
    underlying_key:str
    side:PositionSide
    quantity:int
    average_entry_price:Optional[float]
    realized_pnl:float
    unrealized_pnl:float
    fees:float
    version:int=0

class PositionManager:
    def __init__(self):
        self._positions={}
        self._seen_fills=set()
    def snapshot(self,key):
        return self._positions.get(key,PositionSnapshot(key,PositionSide.FLAT,0,None,0.0,0.0,0.0,0))
    def apply_fill(self,fill):
        if fill.fill_id in self._seen_fills: return self.snapshot(fill.underlying_key)
        old=self.snapshot(fill.underlying_key); buy=fill.side.upper()=="BUY"
        signed=fill.quantity if buy else -fill.quantity
        realized=old.realized_pnl; fees=old.fees+fill.fee
        if old.side==PositionSide.FLAT:
            side=PositionSide.LONG if signed>0 else PositionSide.SHORT
            qty=abs(signed); avg=fill.price
        elif old.side==PositionSide.LONG:
            if signed>0:
                qty=old.quantity+signed
                avg=(old.average_entry_price*old.quantity+fill.price*signed)/qty
                side=PositionSide.LONG
            else:
                closing=min(old.quantity,-signed)
                realized+=(fill.price-old.average_entry_price)*closing
                rem=(-signed)-closing
                if rem: qty,side,avg=rem,PositionSide.SHORT,fill.price
                elif closing<old.quantity: qty,side,avg=old.quantity-closing,PositionSide.LONG,old.average_entry_price
                else: qty,side,avg=0,PositionSide.FLAT,None
        else:
            if signed<0:
                add=-signed; qty=old.quantity+add
                avg=(old.average_entry_price*old.quantity+fill.price*add)/qty
                side=PositionSide.SHORT
            else:
                closing=min(old.quantity,signed)
                realized+=(old.average_entry_price-fill.price)*closing
                rem=signed-closing
                if rem: qty,side,avg=rem,PositionSide.LONG,fill.price
                elif closing<old.quantity: qty,side,avg=old.quantity-closing,PositionSide.SHORT,old.average_entry_price
                else: qty,side,avg=0,PositionSide.FLAT,None
        snap=PositionSnapshot(fill.underlying_key,side,qty,avg,realized,old.unrealized_pnl,fees,old.version+1)
        self._positions[fill.underlying_key]=snap; self._seen_fills.add(fill.fill_id)
        return snap
    def mark_to_market(self,key,mark_price):
        if mark_price<=0: raise ValueError("mark_price_must_be_positive")
        p=self.snapshot(key)
        if p.side==PositionSide.FLAT:return p
        u=(mark_price-p.average_entry_price)*p.quantity if p.side==PositionSide.LONG else (p.average_entry_price-mark_price)*p.quantity
        q=PositionSnapshot(p.underlying_key,p.side,p.quantity,p.average_entry_price,p.realized_pnl,u,p.fees,p.version)
        self._positions[key]=q; return q
    def total_pnl(self,key):
        p=self.snapshot(key); return p.realized_pnl+p.unrealized_pnl-p.fees
