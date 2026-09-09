from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Protocol


class OrderManagerStatus(str, Enum):
    ACTIVE = "ACTIVE"
    PARTIAL = "PARTIAL"
    FILLED = "FILLED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class BrokerUpdate:
    broker_order_id: str
    correlation_id: Optional[str]
    status: OrderManagerStatus
    filled_quantity: int = 0
    remaining_quantity: Optional[int] = None
    average_price: Optional[float] = None


@dataclass(frozen=True)
class OrderRecord:
    client_order_key: str
    trade_id: str
    strategy_id: str
    underlying_key: str
    broker_order_id: Optional[str]
    correlation_id: Optional[str]
    quantity: int
    filled_quantity: int
    remaining_quantity: Optional[int]
    average_price: Optional[float]
    status: OrderManagerStatus
    version: int = 0


class PersistentOrderLedgerProtocol(Protocol):
    def get_by_client_order_key(self, client_order_key: str) -> Optional[OrderRecord]:
        ...

    def get_by_broker_order_id(self, broker_order_id: str) -> Optional[OrderRecord]:
        ...

    def get_by_correlation_id(self, correlation_id: str) -> Optional[OrderRecord]:
        ...

    def upsert_order(self, record: OrderRecord) -> None:
        ...


class OrderManager:
    """
    Restart-safe order-state coordinator.

    It applies broker updates idempotently to a persistent ledger abstraction.
    The ledger is the durable source for order state; an in-memory cache is not
    treated as authoritative.
    """

    _TERMINAL = {
        OrderManagerStatus.FILLED,
        OrderManagerStatus.REJECTED,
        OrderManagerStatus.CANCELLED,
        OrderManagerStatus.EXPIRED,
    }

    def __init__(self, ledger: PersistentOrderLedgerProtocol):
        self.ledger = ledger

    def register_submitted_order(self, record: OrderRecord) -> None:
        existing = self.ledger.get_by_client_order_key(record.client_order_key)

        if existing is not None:
            # Idempotent registration. Do not overwrite a more recent broker state.
            if existing.broker_order_id == record.broker_order_id:
                return
            raise ValueError("client_order_key_already_bound")

        self.ledger.upsert_order(record)

    def apply_broker_update(self, update: BrokerUpdate) -> OrderRecord:
        existing = self.ledger.get_by_broker_order_id(update.broker_order_id)

        if existing is None and update.correlation_id:
            existing = self.ledger.get_by_correlation_id(update.correlation_id)

        if existing is None:
            raise LookupError("broker_update_order_not_found")

        if existing.broker_order_id not in (None, update.broker_order_id):
            raise ValueError("broker_order_id_identity_conflict")

        if existing.status in self._TERMINAL and update.status != existing.status:
            raise ValueError("terminal_order_state_regression")

        if update.filled_quantity < existing.filled_quantity:
            raise ValueError("filled_quantity_regression")

        if update.filled_quantity > existing.quantity:
            raise ValueError("filled_quantity_exceeds_order_quantity")

        next_record = OrderRecord(
            client_order_key=existing.client_order_key,
            trade_id=existing.trade_id,
            strategy_id=existing.strategy_id,
            underlying_key=existing.underlying_key,
            broker_order_id=update.broker_order_id,
            correlation_id=update.correlation_id or existing.correlation_id,
            quantity=existing.quantity,
            filled_quantity=update.filled_quantity,
            remaining_quantity=update.remaining_quantity,
            average_price=update.average_price,
            status=update.status,
            version=existing.version + 1,
        )

        # Duplicate update: avoid needless version churn.
        if (
            existing.status == next_record.status
            and existing.filled_quantity == next_record.filled_quantity
            and existing.remaining_quantity == next_record.remaining_quantity
            and existing.average_price == next_record.average_price
            and existing.broker_order_id == next_record.broker_order_id
        ):
            return existing

        self.ledger.upsert_order(next_record)
        return next_record

    def reconcile_unknown(
        self,
        *,
        client_order_key: str,
        broker_order_id: Optional[str],
        resolved_update: Optional[BrokerUpdate],
    ) -> OrderRecord:
        existing = self.ledger.get_by_client_order_key(client_order_key)

        if existing is None:
            raise LookupError("client_order_key_not_found")

        if resolved_update is None:
            unknown = OrderRecord(
                client_order_key=existing.client_order_key,
                trade_id=existing.trade_id,
                strategy_id=existing.strategy_id,
                underlying_key=existing.underlying_key,
                broker_order_id=broker_order_id or existing.broker_order_id,
                correlation_id=existing.correlation_id,
                quantity=existing.quantity,
                filled_quantity=existing.filled_quantity,
                remaining_quantity=existing.remaining_quantity,
                average_price=existing.average_price,
                status=OrderManagerStatus.UNKNOWN,
                version=existing.version + 1,
            )
            self.ledger.upsert_order(unknown)
            return unknown

        if broker_order_id and resolved_update.broker_order_id != broker_order_id:
            raise ValueError("unknown_resolution_broker_id_mismatch")

        return self.apply_broker_update(resolved_update)
