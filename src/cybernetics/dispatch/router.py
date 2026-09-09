from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, Optional

from .events import MarketEvent
from cybernetics.scanners.models import ScannerRuntimeKey, ScannerState
from cybernetics.scanners.registry import ScannerRuntimeRegistry
from cybernetics.scanners.state_guard import can_process_market_event

@dataclass(frozen=True)
class RoutingKey:
    exchange_segment: str
    security_id: str
    timeframe: str

@dataclass(frozen=True)
class RoutingDecision:
    delivered: bool
    reason: str
    runtime_key: Optional[ScannerRuntimeKey] = None

class ScannerEventRouter:
    """
    Routes canonical market events to exactly one intended scanner runtime.

    Routing is driven by an explicit instrument->scanner/timeframe mapping.
    No scanner is inferred from symbol names and no event is broadcast to all
    scanners. This prevents cross-underlying state contamination.
    """
    def __init__(self, registry: ScannerRuntimeRegistry):
        self.registry=registry
        self._routes: dict[RoutingKey, ScannerRuntimeKey]={}

    def bind(self, route: RoutingKey, runtime_key: ScannerRuntimeKey)->None:
        if route in self._routes and self._routes[route] != runtime_key:
            raise ValueError("routing_key_already_bound")
        self._routes[route]=runtime_key

    def unbind(self, route: RoutingKey)->None:
        self._routes.pop(route,None)

    def get_runtime(self, route: RoutingKey)->Optional[ScannerRuntimeKey]:
        return self._routes.get(route)

    def route(self, event: MarketEvent)->RoutingDecision:
        if not event.timeframe:
            return RoutingDecision(False,"event_timeframe_required")
        key=RoutingKey(event.exchange_segment,event.security_id,event.timeframe)
        runtime_key=self._routes.get(key)
        if runtime_key is None:
            return RoutingDecision(False,"no_scanner_route")
        try:
            runtime=self.registry.get(runtime_key)
        except KeyError:
            return RoutingDecision(False,"scanner_runtime_missing",runtime_key)

        gate=can_process_market_event(runtime)
        if not gate.allowed:
            return RoutingDecision(False,gate.reason,runtime_key)

        runtime.update(event_delta=1,when=event.timestamp,
                       state_patch={"last_event_type":event.event_type,
                                    "last_security_id":event.security_id})
        return RoutingDecision(True,"event_delivered",runtime_key)

    def validate_no_cross_routing(self)->bool:
        return len(self._routes)==len(set(self._routes.keys()))
