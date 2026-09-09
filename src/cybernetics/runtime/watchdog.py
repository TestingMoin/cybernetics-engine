from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Iterable, Protocol
from cybernetics.watchdog.health import HealthRegistry, HealthSupervisor, SupervisorDecision

class WatchdogProbe(Protocol):
    def evaluate(self) -> SupervisorDecision: ...

@dataclass(frozen=True)
class HealthRegistryWatchdogProbe:
    registry: HealthRegistry
    required_components: tuple[str, ...]
    heartbeat_timeout_seconds: float = 15.0
    supervisor: HealthSupervisor | None = None
    now_provider: Callable[[], float] | None = None

    def evaluate(self) -> SupervisorDecision:
        supervisor = self.supervisor or HealthSupervisor()
        kwargs = {"required": self.required_components, "heartbeat_timeout": self.heartbeat_timeout_seconds}
        if self.now_provider is not None:
            kwargs["now"] = self.now_provider()
        return supervisor.evaluate(self.registry, **kwargs)

    def watchdog_healthy(self) -> bool:
        try:
            return not self.evaluate().safe_state_required
        except Exception:
            return False

    def reasons(self) -> tuple[str, ...]:
        try:
            return self.evaluate().reasons
        except Exception as exc:
            return (f"watchdog_probe_error:{type(exc).__name__}",)

def build_watchdog_runtime_wiring(*, registry: HealthRegistry, required_components: Iterable[str], heartbeat_timeout_seconds: float = 15.0,
                                  supervisor: HealthSupervisor | None = None, now_provider: Callable[[], float] | None = None) -> HealthRegistryWatchdogProbe:
    if registry is None:
        raise ValueError("watchdog_registry_required")
    required = tuple(dict.fromkeys(str(name) for name in required_components if str(name)))
    if not required:
        raise ValueError("watchdog_required_components_required")
    if heartbeat_timeout_seconds <= 0:
        raise ValueError("watchdog_heartbeat_timeout_must_be_positive")
    return HealthRegistryWatchdogProbe(registry, required, heartbeat_timeout_seconds, supervisor, now_provider)
