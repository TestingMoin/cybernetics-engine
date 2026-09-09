from cybernetics.brokers.interface import BrokerOrderRequest
from cybernetics.execution.paper import PaperBrokerAdapter
from cybernetics.paper.order import PaperBroker


def test_paper_market_order_never_requires_live_authorization():
    adapter = PaperBrokerAdapter(
        paper_broker=PaperBroker(fee_bps=0, slippage_bps=0),
        market_price_provider=lambda symbol: 100.0,
    )

    result = adapter.place_order(
        BrokerOrderRequest(
            symbol="TEST",
            side="BUY",
            quantity=10,
            order_type="MARKET",
        )
    )

    assert result.accepted is True
    assert result.status == "FILLED"
    assert result.broker == "PAPER"
    assert result.broker_order_id is not None


def test_paper_order_updates_position():
    broker = PaperBroker(fee_bps=0, slippage_bps=0)
    adapter = PaperBrokerAdapter(
        paper_broker=broker,
        market_price_provider=lambda symbol: 100.0,
    )

    result = adapter.place_order(
        BrokerOrderRequest(
            symbol="TEST",
            side="BUY",
            quantity=5,
            order_type="MARKET",
        )
    )

    assert result.accepted is True
    assert broker.positions["TEST"].quantity == 5
    assert broker.positions["TEST"].avg_price == 100.0


def test_paper_limit_order_remains_open_until_limit_processing():
    broker = PaperBroker(fee_bps=0, slippage_bps=0)
    adapter = PaperBrokerAdapter(
        paper_broker=broker,
        market_price_provider=lambda symbol: 105.0,
    )

    result = adapter.place_order(
        BrokerOrderRequest(
            symbol="TEST",
            side="BUY",
            quantity=5,
            order_type="LIMIT",
            limit_price=100.0,
        )
    )

    assert result.accepted is True
    assert result.status == "OPEN"
    assert broker.positions == {}

    assert broker.process_limit(result.broker_order_id, 99.0) is True
    assert broker.positions["TEST"].quantity == 5


def test_paper_adapter_has_no_live_io():
    adapter = PaperBrokerAdapter(
        market_price_provider=lambda symbol: 100.0,
    )

    health = adapter.health()

    assert health["broker"] == "PAPER"
    assert health["simulation_only"] is True
    assert health["live_io_enabled"] is False
