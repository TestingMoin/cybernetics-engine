from dataclasses import dataclass
from typing import Optional
import time, uuid

@dataclass(frozen=True)
class PaperOrder:
    order_id: str
    symbol: str
    side: str
    quantity: int
    order_type: str
    limit_price: Optional[float]
    submitted_at: float

@dataclass(frozen=True)
class Fill:
    fill_id: str
    order_id: str
    quantity: int
    price: float
    fee: float
    slippage: float
    timestamp: float

@dataclass
class PaperPosition:
    symbol: str
    quantity: int = 0
    avg_price: float = 0.0
    realized_pnl: float = 0.0

class PaperBroker:
    """Simulation-only broker; no Dhan calls."""
    def __init__(self, fee_bps=5.0, slippage_bps=1.0):
        self.fee_bps=max(0.0,float(fee_bps))
        self.slippage_bps=max(0.0,float(slippage_bps))
        self.orders={}
        self.fills=[]
        self.positions={}

    def submit(self, symbol, side, quantity, order_type, market_price, limit_price=None):
        if quantity <= 0 or market_price <= 0:
            raise ValueError("quantity and market_price must be positive")
        if order_type=="LIMIT" and (limit_price is None or limit_price <= 0):
            raise ValueError("limit order requires positive limit_price")
        oid=str(uuid.uuid4())
        order=PaperOrder(oid,symbol,side,quantity,order_type,limit_price,time.time())
        self.orders[oid]=order
        if order_type=="MARKET":
            self._fill(order,market_price,quantity)
        return order

    def _fill(self, order, market_price, quantity):
        slip=market_price*self.slippage_bps/10000.0
        price=market_price+slip if order.side=="BUY" else market_price-slip
        fee=price*quantity*self.fee_bps/10000.0
        fill=Fill(str(uuid.uuid4()),order.order_id,quantity,price,fee,slip,time.time())
        self.fills.append(fill)
        p=self.positions.setdefault(order.symbol,PaperPosition(order.symbol))
        signed=quantity if order.side=="BUY" else -quantity
        if p.quantity==0:
            p.quantity=signed; p.avg_price=price
        elif (p.quantity>0)==(signed>0):
            total=abs(p.quantity)+abs(signed)
            p.avg_price=(abs(p.quantity)*p.avg_price+abs(signed)*price)/total
            p.quantity+=signed
        else:
            closing=min(abs(p.quantity),abs(signed))
            pnl=(price-p.avg_price)*closing*(1 if p.quantity>0 else -1)
            p.realized_pnl += pnl-fee
            p.quantity += signed
            if p.quantity==0: p.avg_price=0.0

    def process_limit(self, order_id, market_price):
        o=self.orders[order_id]
        if o.order_type!="LIMIT" or o.limit_price is None:
            return False
        ok=(o.side=="BUY" and market_price<=o.limit_price) or (o.side=="SELL" and market_price>=o.limit_price)
        if ok:
            self._fill(o,o.limit_price,o.quantity)
        return ok
