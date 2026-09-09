from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from cybernetics.brokers.interface import BrokerAdapter


@dataclass(frozen=True)
class BrokerRuntimeWiring:
    """Read-only runtime boundary for broker availability/auth state.

    The adapter itself remains responsible for broker I/O.  This boundary only
    evaluates an injected readiness/health policy and never places/cancels orders.
    """

    broker: BrokerAdapter
    readiness: Callable[[BrokerAdapter], bool] | None = None

    def broker_available(self) -> bool:
        check = self.readiness or self._default_readiness
        try:
            return bool(check(self.broker))
        except Exception:
            return False

    def health(self) -> Mapping[str, Any]:
        try:
            report = self.broker.health()
            return dict(report) if isinstance(report, Mapping) else {"valid": False}
        except Exception as exc:
            return {"valid": False, "probe_error": type(exc).__name__}

    def reasons(self) -> tuple[str, ...]:
        report = self.health()
        reasons: list[str] = []
        if report.get("valid") is False:
            reasons.append("broker_health_invalid")
        if report.get("configured") is False:
            reasons.append("broker_not_configured")
        if report.get("authenticated") is False:
            reasons.append("broker_not_authenticated")
        return tuple(dict.fromkeys(reasons))

    @staticmethod
    def _default_readiness(component: BrokerAdapter) -> bool:
        report = component.health()
        if not isinstance(report, Mapping):
            return False
        if report.get("valid") is False:
            return False
        if report.get("configured") is False:
            return False
        if report.get("authenticated") is False:
            return False
        # Legacy adapters may report only configured=True; that is not enough
        # to claim authentication failure, but no configured broker remains
        # insufficient.  The concrete readiness policy may enforce stronger
        # production requirements when the adapter exposes them.
        return True


def build_broker_runtime_wiring(
    *,
    broker: BrokerAdapter,
    readiness: Callable[[BrokerAdapter], bool] | None = None,
) -> BrokerRuntimeWiring:
    if broker is None:
        raise ValueError("broker_adapter_required")
    return BrokerRuntimeWiring(broker=broker, readiness=readiness)
