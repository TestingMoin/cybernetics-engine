from __future__ import annotations
from dataclasses import dataclass
from .coordinator import ExecutionCoordinator, ExecutionContext
from cybernetics.brokers.router import MultiBrokerRouter
from cybernetics.brokers.interface import BrokerOrderRequest, BrokerOrderResult

@dataclass(frozen=True)
class PipelineResult:
    executed: bool
    status: str
    reason: str
    broker_result: BrokerOrderResult | None = None

class ExecutionPipeline:
    def __init__(self, coordinator: ExecutionCoordinator, router: MultiBrokerRouter):
        self.coordinator = coordinator
        self.router = router

    def execute(self, ctx: ExecutionContext, route_id: str,
                order: BrokerOrderRequest) -> PipelineResult:
        decision = self.coordinator.authorize(ctx)
        if not decision.allowed:
            return PipelineResult(False, "BLOCKED", decision.reason)
        result = self.router.place(route_id, order)
        if not result.accepted:
            return PipelineResult(False, result.status, result.message, result)
        return PipelineResult(True, result.status, "broker_accepted", result)
