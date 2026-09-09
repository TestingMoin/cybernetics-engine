from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Any


class ExecutionAction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"


@dataclass(frozen=True)
class ExecutionIntent:
    """
    Broker-neutral, immutable execution command.

    This is an instruction for the execution layer, not a broker API payload.
    """
    intent_id: str
    trade_id: str
    strategy_id: str
    strategy_version: str
    signal_id: str
    underlying_key: str
    action: ExecutionAction
    order_type: OrderType
    quantity: int
    limit_price: Optional[float] = None
    product_type: str = "INTRADAY"
    validity: str = "DAY"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.intent_id or not self.trade_id or not self.strategy_id:
            raise ValueError("execution_intent_identity_required")
        if not self.strategy_version or not self.signal_id or not self.underlying_key:
            raise ValueError("execution_intent_context_required")
        if self.quantity <= 0:
            raise ValueError("execution_quantity_must_be_positive")

        if self.order_type == OrderType.LIMIT:
            if self.limit_price is None or self.limit_price <= 0:
                raise ValueError("limit_price_required_for_limit_order")

        if self.order_type == OrderType.MARKET and self.limit_price is not None:
            raise ValueError("market_order_cannot_have_limit_price")


@dataclass(frozen=True)
class ExecutionIntentBuilder:
    """
    Converts an already-approved pre-trade decision into a broker-neutral intent.

    It does not:
    - call a broker
    - add a broker security ID
    - perform order submission
    - override pre-trade approval
    """

    def build(
        self,
        *,
        approved: bool,
        trade_id: str,
        strategy_id: str,
        strategy_version: str,
        signal_id: str,
        underlying_key: str,
        action: str,
        quantity: int,
        order_type: str = "MARKET",
        limit_price: Optional[float] = None,
        product_type: str = "INTRADAY",
        validity: str = "DAY",
        metadata: Optional[dict[str, Any]] = None,
    ) -> ExecutionIntent:
        if not approved:
            raise PermissionError("pretrade_approval_required")

        try:
            normalized_action = ExecutionAction(str(action).upper())
        except ValueError:
            raise ValueError("unsupported_execution_action")

        try:
            normalized_order_type = OrderType(str(order_type).upper())
        except ValueError:
            raise ValueError("unsupported_order_type")

        if not product_type or not validity:
            raise ValueError("execution_terms_required")

        intent_id = f"{trade_id}:{signal_id}:{normalized_action.value}:{quantity}:{normalized_order_type.value}"

        return ExecutionIntent(
            intent_id=intent_id,
            trade_id=trade_id,
            strategy_id=strategy_id,
            strategy_version=strategy_version,
            signal_id=signal_id,
            underlying_key=underlying_key,
            action=normalized_action,
            order_type=normalized_order_type,
            quantity=quantity,
            limit_price=limit_price,
            product_type=product_type,
            validity=validity,
            metadata=metadata or {},
        )
