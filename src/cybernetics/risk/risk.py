from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class AccountRisk:
    available_capital: float
    day_start_equity: float
    realized_pnl: float
    unrealized_pnl: float
    max_daily_loss: float
    max_total_exposure: float
    max_open_positions: int

    @property
    def current_equity(self) -> float:
        return self.day_start_equity + self.realized_pnl + self.unrealized_pnl

    @property
    def daily_drawdown(self) -> float:
        return max(0.0, self.day_start_equity - self.current_equity)

@dataclass(frozen=True)
class InstrumentRisk:
    symbol: str
    quantity: int
    lot_size: int
    price: float
    stop_price: Optional[float]
    side: str
    margin_required: float
    max_position_quantity: int

    @property
    def notional(self) -> float:
        return abs(self.quantity) * self.price

    @property
    def stop_risk(self) -> Optional[float]:
        if self.stop_price is None:
            return None
        return abs(self.price-self.stop_price) * abs(self.quantity)

@dataclass(frozen=True)
class RiskDecision:
    approved: bool
    reasons: tuple[str,...]
    allowed_quantity: int
    requested_quantity: int
    daily_drawdown: float
    exposure_after: float
    margin_required: float

class RiskEngine:
    """
    Deterministic system/strategy risk gate.
    It never places, modifies, or cancels broker orders.
    """
    def evaluate(self, account: AccountRisk, order: InstrumentRisk,
                 current_exposure: float = 0.0) -> RiskDecision:
        reasons=[]
        qty=order.quantity
        if qty <= 0: reasons.append("invalid_quantity")
        if order.lot_size <= 0: reasons.append("invalid_lot_size")
        if order.price <= 0: reasons.append("invalid_price")
        if order.max_position_quantity <= 0: reasons.append("invalid_position_limit")
        if account.available_capital < 0: reasons.append("invalid_available_capital")
        if account.max_open_positions <= 0: reasons.append("invalid_open_position_limit")
        if account.daily_drawdown >= account.max_daily_loss:
            reasons.append("daily_loss_limit_reached")
        if current_exposure + order.notional > account.max_total_exposure:
            reasons.append("exposure_limit_exceeded")
        if order.quantity > order.max_position_quantity:
            reasons.append("position_limit_exceeded")
        if order.margin_required > account.available_capital:
            reasons.append("insufficient_margin")

        # Quantity must respect exchange lot granularity.
        if order.quantity % order.lot_size != 0:
            reasons.append("quantity_not_lot_aligned")

        approved = not reasons
        allowed = order.quantity if approved else 0
        return RiskDecision(
            approved, tuple(reasons), allowed, order.quantity,
            account.daily_drawdown, current_exposure + (order.notional if approved else 0),
            order.margin_required
        )
