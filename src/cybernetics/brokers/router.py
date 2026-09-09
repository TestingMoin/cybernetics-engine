from dataclasses import dataclass
from typing import Dict
from .interface import BrokerAdapter, BrokerOrderRequest, BrokerOrderResult

@dataclass(frozen=True)
class BrokerRoute:
    route_id: str
    broker_name: str
    adapter: BrokerAdapter
    enabled: bool = False

class MultiBrokerRouter:
    def __init__(self):
        self._routes: Dict[str, BrokerRoute] = {}

    def register(self, route: BrokerRoute) -> None:
        if route.route_id in self._routes:
            raise ValueError(f"duplicate route_id: {route.route_id}")
        self._routes[route.route_id] = route

    def enable(self, route_id: str) -> None:
        r = self._routes[route_id]
        self._routes[route_id] = BrokerRoute(r.route_id, r.broker_name, r.adapter, True)

    def disable(self, route_id: str) -> None:
        r = self._routes[route_id]
        self._routes[route_id] = BrokerRoute(r.route_id, r.broker_name, r.adapter, False)

    def list_routes(self) -> list[BrokerRoute]:
        return list(self._routes.values())

    def place(self, route_id: str, request: BrokerOrderRequest) -> BrokerOrderResult:
        route = self._routes[route_id]
        if not route.enabled:
            return BrokerOrderResult(route.broker_name, False, None, "BLOCKED", "route_disabled")
        return route.adapter.place_order(request)

class NullBrokerAdapter(BrokerAdapter):
    name = "NULL"
    def health(self): return {"broker": self.name, "ok": True}
    def get_positions(self): return []
    def get_orders(self): return []
    def place_order(self, request):
        return BrokerOrderResult(self.name, False, None, "BLOCKED", "null_adapter")
    def cancel_order(self, broker_order_id):
        return BrokerOrderResult(self.name, False, broker_order_id, "BLOCKED", "null_adapter")
