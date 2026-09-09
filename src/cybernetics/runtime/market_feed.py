from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol


class MarketFeedProbe(Protocol):
    def safe_for_market_state(self) -> bool: ...


@dataclass(frozen=True)
class MarketFeedRuntimeWiring:
    """Runtime boundary for the canonical market-feed supervisor.

    The wiring layer is intentionally side-effect free. It does not open a
    websocket, subscribe instruments, reconnect, or mutate market state. The
    supplied supervisor owns those operational responsibilities.
    """

    supervisor: MarketFeedProbe
    readiness: Callable[[MarketFeedProbe], bool] | None = None

    def market_data_ready(self) -> bool:
        check = self.readiness or (lambda component: component.safe_for_market_state())
        try:
            return bool(check(self.supervisor))
        except Exception:
            return False

    def unhealthy(self) -> bool:
        return not self.market_data_ready()


def build_market_feed_wiring(
    *,
    supervisor: MarketFeedProbe,
    readiness: Callable[[MarketFeedProbe], bool] | None = None,
) -> MarketFeedRuntimeWiring:
    """Construct the canonical market-feed runtime boundary."""
    if supervisor is None:
        raise ValueError("market_feed_supervisor_required")
    return MarketFeedRuntimeWiring(supervisor=supervisor, readiness=readiness)
