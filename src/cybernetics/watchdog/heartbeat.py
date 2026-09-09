from __future__ import annotations
import asyncio, time
from dataclasses import dataclass
from .health import HealthRegistry, Health

@dataclass(frozen=True)
class HeartbeatConfig:
    interval_seconds: float = 5.0
    component: str = "engine"

class HeartbeatLoop:
    def __init__(self, registry: HealthRegistry, config: HeartbeatConfig | None=None):
        self.registry=registry
        self.config=config or HeartbeatConfig()

    async def run(self, stop_event: asyncio.Event):
        while not stop_event.is_set():
            self.registry.beat(self.config.component, health=Health.HEALTHY, now=time.time())
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=self.config.interval_seconds)
            except asyncio.TimeoutError:
                continue
