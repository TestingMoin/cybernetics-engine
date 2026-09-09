from .interface import BrokerAdapter, BrokerOrderRequest, BrokerOrderResult

class DhanV2Adapter(BrokerAdapter):
    name = "DHAN_V2"

    def __init__(self, transport=None):
        self.transport = transport

    def health(self):
        return {
            "broker": self.name,
            "configured": self.transport is not None,
            "live_io_enabled": False,
        }

    def get_positions(self):
        return []

    def get_orders(self):
        return []

    def place_order(self, request: BrokerOrderRequest):
        return BrokerOrderResult(
            self.name, False, None, "BLOCKED",
            "live_execution_not_enabled_in_chunk23"
        )

    def cancel_order(self, broker_order_id: str):
        return BrokerOrderResult(
            self.name, False, broker_order_id, "BLOCKED",
            "live_execution_not_enabled_in_chunk23"
        )
