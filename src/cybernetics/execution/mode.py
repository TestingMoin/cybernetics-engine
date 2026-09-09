from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from cybernetics.brokers.interface import BrokerOrderRequest, BrokerOrderResult
from cybernetics.execution.coordinator import ExecutionContext, ExecutionCoordinator
from cybernetics.execution.paper import PaperBrokerAdapter


class ExecutionMode(str, Enum):
    PAPER = "PAPER"
    LIVE = "LIVE"


@dataclass(frozen=True)
class ModeExecutionResult:
    executed: bool
    mode: ExecutionMode
    status: str
    reason: str
    broker_result: BrokerOrderResult | None = None


class ModeExecutionRouter:
    """
    Selects the execution destination after the existing execution controls.

    PAPER:
        Uses only PaperBrokerAdapter. No live authorization is required.

    LIVE:
        Requires the existing ExecutionCoordinator authorization and therefore
        retains the existing live authorization safety boundary.
    """

    def __init__(
        self,
        *,
        paper_adapter: PaperBrokerAdapter,
        live_router=None,
        coordinator: ExecutionCoordinator | None = None,
    ):
        self.paper_adapter = paper_adapter
        self.live_router = live_router
        self.coordinator = coordinator or ExecutionCoordinator()

    def execute(
        self,
        *,
        mode: ExecutionMode | str,
        ctx: ExecutionContext,
        order: BrokerOrderRequest,
        route_id: str | None = None,
    ) -> ModeExecutionResult:

        if isinstance(mode, ExecutionMode):
            selected = mode
        else:
            selected = ExecutionMode(str(mode).upper())

        if selected == ExecutionMode.PAPER:
            result = self.paper_adapter.place_order(order)

            return ModeExecutionResult(
                executed=result.accepted,
                mode=selected,
                status=result.status,
                reason=result.message,
                broker_result=result,
            )

        # LIVE deliberately retains the existing coordinator.
        decision = self.coordinator.authorize(ctx)

        if not decision.allowed:
            return ModeExecutionResult(
                executed=False,
                mode=selected,
                status="BLOCKED",
                reason=decision.reason,
            )

        if self.live_router is None:
            return ModeExecutionResult(
                executed=False,
                mode=selected,
                status="BLOCKED",
                reason="live_router_required",
            )

        if route_id is None:
            return ModeExecutionResult(
                executed=False,
                mode=selected,
                status="BLOCKED",
                reason="live_route_required",
            )

        result = self.live_router.place(route_id, order)

        return ModeExecutionResult(
            executed=result.accepted,
            mode=selected,
            status=result.status,
            reason=result.message,
            broker_result=result,
        )
