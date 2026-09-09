from cybernetics.brokers.interface import BrokerOrderRequest, BrokerOrderResult
from cybernetics.execution.coordinator import ExecutionContext
from cybernetics.execution.mode import ExecutionMode, ModeExecutionRouter
from cybernetics.execution.paper import PaperBrokerAdapter
from cybernetics.paper.order import PaperBroker


def ctx(**overrides):
    values = dict(
        engine_running=True,
        live_authorized=False,
        emergency_stop=False,
        risk_approved=True,
        pretrade_approved=True,
        reconciliation_ok=True,
        broker_available=True,
    )
    values.update(overrides)
    return ExecutionContext(**values)


def test_paper_mode_does_not_require_live_authorization():
    adapter = PaperBrokerAdapter(
        paper_broker=PaperBroker(fee_bps=0, slippage_bps=0),
        market_price_provider=lambda symbol: 100.0,
    )
    router = ModeExecutionRouter(paper_adapter=adapter)

    result = router.execute(
        mode=ExecutionMode.PAPER,
        ctx=ctx(),
        order=BrokerOrderRequest("TEST", "BUY", 10, "MARKET"),
    )

    assert result.executed is True
    assert result.mode == ExecutionMode.PAPER
    assert result.status == "FILLED"


def test_live_mode_still_requires_live_authorization():
    adapter = PaperBrokerAdapter(
        paper_broker=PaperBroker(),
        market_price_provider=lambda symbol: 100.0,
    )
    router = ModeExecutionRouter(paper_adapter=adapter)

    result = router.execute(
        mode=ExecutionMode.LIVE,
        ctx=ctx(live_authorized=False),
        order=BrokerOrderRequest("TEST", "BUY", 1, "MARKET"),
        route_id="DHAN",
    )

    assert result.executed is False
    assert result.status == "BLOCKED"
    assert result.reason == "live_not_authorized"


class RejectingLiveRouter:
    def place(self, route_id, request):
        return BrokerOrderResult(
            "TEST_LIVE",
            False,
            None,
            "BLOCKED",
            "test_live_router",
        )


def test_live_route_is_only_reached_after_authorization():
    adapter = PaperBrokerAdapter(
        paper_broker=PaperBroker(),
        market_price_provider=lambda symbol: 100.0,
    )
    router = ModeExecutionRouter(
        paper_adapter=adapter,
        live_router=RejectingLiveRouter(),
    )

    result = router.execute(
        mode=ExecutionMode.LIVE,
        ctx=ctx(live_authorized=True),
        order=BrokerOrderRequest("TEST", "BUY", 1, "MARKET"),
        route_id="DHAN",
    )

    assert result.executed is False
    assert result.reason == "test_live_router"


def test_invalid_paper_price_is_rejected_without_live_path():
    adapter = PaperBrokerAdapter(
        paper_broker=PaperBroker(),
        market_price_provider=lambda symbol: 0.0,
    )
    router = ModeExecutionRouter(paper_adapter=adapter)

    result = router.execute(
        mode="PAPER",
        ctx=ctx(),
        order=BrokerOrderRequest("TEST", "BUY", 1, "MARKET"),
    )

    assert result.executed is False
    assert result.status == "REJECTED"
    assert result.mode == ExecutionMode.PAPER
