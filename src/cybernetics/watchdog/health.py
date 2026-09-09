from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
import time

class Health(str, Enum):
    HEALTHY="HEALTHY"
    DEGRADED="DEGRADED"
    FAILED="FAILED"
    UNKNOWN="UNKNOWN"

@dataclass
class ComponentState:
    name: str
    health: Health = Health.UNKNOWN
    last_heartbeat: float | None = None
    detail: str = ""
    metadata: dict = field(default_factory=dict)

class HealthRegistry:
    def __init__(self):
        self._states: dict[str, ComponentState] = {}

    def beat(self, name: str, *, health: Health = Health.HEALTHY, detail: str = "", now: float | None = None, **metadata):
        t=time.time() if now is None else now
        s=self._states.setdefault(name, ComponentState(name))
        s.health=health; s.last_heartbeat=t; s.detail=detail; s.metadata=dict(metadata)

    def fail(self, name: str, detail: str, *, now: float | None = None):
        self.beat(name, health=Health.FAILED, detail=detail, now=now)

    def get(self, name: str) -> ComponentState:
        return self._states.get(name, ComponentState(name))

    def all(self) -> list[ComponentState]:
        return list(self._states.values())

    def stale(self, timeout_seconds: float, *, now: float | None = None) -> list[str]:
        t=time.time() if now is None else now
        return [s.name for s in self._states.values() if s.last_heartbeat is None or t-s.last_heartbeat > timeout_seconds]

@dataclass(frozen=True)
class SupervisorDecision:
    safe_state_required: bool
    reasons: tuple[str,...]

class HealthSupervisor:
    def evaluate(self, registry: HealthRegistry, *, required: tuple[str,...], heartbeat_timeout: float,
                 now: float | None = None) -> SupervisorDecision:
        reasons=[]
        for name in required:
            state=registry.get(name)
            if state.health in {Health.FAILED, Health.DEGRADED}:
                reasons.append(f"{name}:{state.health.value}")
            if state.last_heartbeat is None:
                reasons.append(f"{name}:no_heartbeat")
        for name in registry.stale(heartbeat_timeout, now=now):
            if name in required:
                reasons.append(f"{name}:stale_heartbeat")
        unique=tuple(dict.fromkeys(reasons))
        return SupervisorDecision(bool(unique), unique)
