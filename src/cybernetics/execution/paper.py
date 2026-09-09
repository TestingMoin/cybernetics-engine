from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from cybernetics.brokers.interface import (
    BrokerAdapter,
    BrokerOrderRequest,
    BrokerOrderResult,
)
from cybernetics.paper.order import PaperBroker


@dataclass(frozen=True)
class PaperExecutionResult:
    accepted: bool
    order_id: str | None
    status: str
    message: str


class PaperBrokerAdapter(BrokerAdapter):
    """
    BrokerAdapter-compatible paper execution boundary.

    This adapter is simulation-only:
    - never calls Dhan
    - never consumes broker credentials
    - never uses broker transport
    - obtains market prices only through the injected price provider
    """

    name = "PAPER"

    def __init__(
        self,
        paper_broker: PaperBroker | None = None,
        market_price_provider: Callable[[str], float] | None = None,
    ):
        self.paper_broker = paper_broker or PaperBroker()
        self.market_price_provider = market_price_provider

    def health(self) -> dict:
        return {
            "broker": self.name,
            "ok": True,
            "simulation_only": True,
            "live_io_enabled": False,
        }

    def get_positions(self) -> list[dict]:
        return [
            {
                "symbol": position.symbol,
                "quantity": position.quantity,
                "avg_price": position.avg_price,
                "realized_pnl": position.realized_pnl,
            }
            for position in self.paper_broker.positions.values()
        ]

    def get_orders(self) -> list[dict]:
        return [
            {
                "order_id": order.order_id,
                "symbol": order.symbol,
                "side": order.side,
                "quantity": order.quantity,
                "order_type": order.order_type,
                "limit_price": order.limit_price,
                "submitted_at": order.submitted_at,
            }
            for order in self.paper_broker.orders.values()
        ]

    def place_order(self, request: BrokerOrderRequest) -> BrokerOrderResult:
        if self.market_price_provider is None:
            return BrokerOrderResult(
                broker=self.name,
                accepted=False,
                broker_order_id=None,
                status="BLOCKED",
                message="paper_market_price_provider_required",
            )

        if request.quantity <= 0:
            return BrokerOrderResult(
                broker=self.name,
                accepted=False,
                broker_order_id=None,
                status="REJECTED",
                message="quantity_invalid",
            )

        try:
            market_price = float(self.market_price_provider(request.symbol))
        except Exception as exc:
            return BrokerOrderResult(
                broker=self.name,
                accepted=False,
                broker_order_id=None,
                status="REJECTED",
                message=f"paper_market_price_error:{type(exc).__name__}",
            )

        if market_price <= 0:
            return BrokerOrderResult(
                broker=self.name,
                accepted=False,
                broker_order_id=None,
                status="REJECTED",
                message="market_price_invalid",
            )

        try:
            order = self.paper_broker.submit(
                symbol=request.symbol,
                side=request.side.upper(),
                quantity=request.quantity,
                order_type=request.order_type.upper(),
                market_price=market_price,
                limit_price=request.limit_price,
            )
        except ValueError as exc:
            return BrokerOrderResult(
                broker=self.name,
                accepted=False,
                broker_order_id=None,
                status="REJECTED",
                message=str(exc),
            )

        return BrokerOrderResult(
            broker=self.name,
            accepted=True,
            broker_order_id=order.order_id,
            status="FILLED" if request.order_type.upper() == "MARKET" else "OPEN",
            message="paper_order_accepted",
        )

    def cancel_order(self, broker_order_id: str) -> BrokerOrderResult:
        order = self.paper_broker.orders.get(broker_order_id)
        if order is None:
            return BrokerOrderResult(
                broker=self.name,
                accepted=False,
                broker_order_id=broker_order_id,
                status="REJECTED",
                message="paper_order_not_found",
            )

        return BrokerOrderResult(
            broker=self.name,
            accepted=False,
            broker_order_id=broker_order_id,
            status="BLOCKED",
            message="paper_cancel_not_supported",
        )
