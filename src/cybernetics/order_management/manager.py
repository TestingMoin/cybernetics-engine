from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional

from .idempotency import IdempotencyRecord, IdempotencyStore
from cybernetics.brokers.interface import BrokerOrderRequest, BrokerOrderResult

class OrderState(str, Enum):
    NEW = "NEW"
    SUBMITTING = "SUBMITTING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    UNKNOWN = "UNKNOWN"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    CANCELLED = "CANCELLED"

@dataclass
class ManagedOrder:
    client_order_key: str
    request: BrokerOrderRequest
    state: OrderState = OrderState.NEW
    broker_order_id: Optional[str] = None
    message: str = ""

class OrderManager:
    """
    Exactly-once submission guard at the client-order-key level.
    A retry of an already-submitted key never invokes the broker again.
    Unknown broker outcomes are retained as UNKNOWN rather than guessed.
    """
    def __init__(self, broker_submit: Callable[[BrokerOrderRequest], BrokerOrderResult],
                 store: Optional[IdempotencyStore] = None):
        self._submit = broker_submit
        self._store = store or IdempotencyStore()
        self._orders: dict[str, ManagedOrder] = {}

    def submit(self, client_order_key: str,
               request: BrokerOrderRequest) -> ManagedOrder:
        existing = self._orders.get(client_order_key)
        if existing is not None:
            return existing

        order = ManagedOrder(client_order_key, request, OrderState.SUBMITTING)
        self._orders[client_order_key] = order

        try:
            result = self._submit(request)
        except TimeoutError as exc:
            # Broker outcome may be unknown; never blindly retry.
            order.state = OrderState.UNKNOWN
            order.message = str(exc) or "broker_timeout_unknown_outcome"
            self._store.put_once(IdempotencyRecord(client_order_key, None, order.state.value))
            return order
        except Exception as exc:
            order.state = OrderState.REJECTED
            order.message = f"broker_exception:{type(exc).__name__}"
            self._store.put_once(IdempotencyRecord(client_order_key, None, order.state.value))
            return order

        if result.accepted:
            order.state = OrderState.ACCEPTED
            order.broker_order_id = result.broker_order_id
        else:
            order.state = OrderState.REJECTED
        order.message = result.message
        self._store.put_once(
            IdempotencyRecord(client_order_key, result.broker_order_id, order.state.value)
        )
        return order

    def get(self, client_order_key: str) -> Optional[ManagedOrder]:
        return self._orders.get(client_order_key)
