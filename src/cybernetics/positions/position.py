from dataclasses import dataclass
from typing import Optional

@dataclass
class Position:
    symbol: str
    quantity: int = 0
    avg_price: float = 0.0
    realized_pnl: float = 0.0
    last_price: Optional[float] = None
    fees: float = 0.0

    @property
    def side(self) -> str:
        if self.quantity > 0: return "LONG"
        if self.quantity < 0: return "SHORT"
        return "FLAT"

    @property
    def unrealized_pnl(self) -> float:
        if self.quantity == 0 or self.last_price is None:
            return 0.0
        if self.quantity > 0:
            return (self.last_price - self.avg_price) * self.quantity
        return (self.avg_price - self.last_price) * abs(self.quantity)

class PositionManager:
    """Maintains position state from executed fills. No broker calls."""
    def __init__(self):
        self.positions = {}

    def apply_fill(self, symbol: str, side: str, quantity: int, price: float, fee: float = 0.0) -> Position:
        if quantity <= 0 or price <= 0:
            raise ValueError("quantity and price must be positive")
        if side not in {"BUY","SELL"}:
            raise ValueError("side must be BUY or SELL")
        p=self.positions.setdefault(symbol, Position(symbol))
        signed=quantity if side=="BUY" else -quantity
        p.fees += fee

        if p.quantity == 0:
            p.quantity=signed
            p.avg_price=price
            return p

        same=(p.quantity>0)==(signed>0)
        if same:
            total=abs(p.quantity)+abs(signed)
            p.avg_price=(abs(p.quantity)*p.avg_price+abs(signed)*price)/total
            p.quantity += signed
            return p

        closing=min(abs(p.quantity), abs(signed))
        pnl=(price-p.avg_price)*closing*(1 if p.quantity>0 else -1)
        p.realized_pnl += pnl-fee
        prior_sign = 1 if p.quantity > 0 else -1
        p.quantity += signed
        if p.quantity==0:
            p.avg_price=0.0
        elif (p.quantity > 0 and prior_sign < 0) or (p.quantity < 0 and prior_sign > 0):
            # Reversal: residual position is entirely the new fill at its fill price.
            p.avg_price=price
        return p

    def mark(self, symbol: str, last_price: float) -> Position:
        if last_price <= 0:
            raise ValueError("last_price must be positive")
        if symbol not in self.positions:
            self.positions[symbol]=Position(symbol)
        self.positions[symbol].last_price=last_price
        return self.positions[symbol]

    def get(self, symbol: str) -> Position:
        return self.positions.setdefault(symbol, Position(symbol))
