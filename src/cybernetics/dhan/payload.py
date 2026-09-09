from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Any
import hashlib

from cybernetics.execution.intent import ExecutionAction, OrderType
from cybernetics.execution.binding import BoundExecutionInstruction


_DHAN_ORDER_TYPES = {"MARKET", "LIMIT", "STOP_LOSS", "STOP_LOSS_MARKET"}
_DHAN_PRODUCTS = {"CNC", "INTRADAY", "MARGIN", "MTF", "CO", "BO"}
_DHAN_VALIDITY = {"DAY", "IOC"}
_DHAN_SEGMENTS = {"NSE_EQ", "NSE_FNO", "NSE_CURRENCY", "BSE_EQ", "MCX_COMM"}


@dataclass(frozen=True)
class DhanOrderPayload:
    """
    Exact Dhan V2 order request structure, kept separate from credentials.

    This object is a serializable payload only. It performs no HTTP request.
    """
    dhanClientId: str
    correlationId: str
    transactionType: str
    exchangeSegment: str
    productType: str
    orderType: str
    validity: str
    securityId: str
    quantity: int
    disclosedQuantity: int = 0
    price: float = 0.0
    triggerPrice: float = 0.0
    afterMarketOrder: bool = False
    amoTime: str = ""
    boProfitValue: float = 0.0
    boStopLossValue: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "dhanClientId": self.dhanClientId,
            "correlationId": self.correlationId,
            "transactionType": self.transactionType,
            "exchangeSegment": self.exchangeSegment,
            "productType": self.productType,
            "orderType": self.orderType,
            "validity": self.validity,
            "securityId": self.securityId,
            "quantity": self.quantity,
            "disclosedQuantity": self.disclosedQuantity,
            "price": self.price,
            "triggerPrice": self.triggerPrice,
            "afterMarketOrder": self.afterMarketOrder,
            "amoTime": self.amoTime,
            "boProfitValue": self.boProfitValue,
            "boStopLossValue": self.boStopLossValue,
        }


class DhanOrderPayloadMapper:
    """
    Adapter-bound mapper for Dhan V2.

    Credentials/tokens are intentionally not accepted. The caller supplies the
    Dhan client ID, while the authentication layer remains responsible for the
    access-token header.

    Current Dhan V2 order placement requires fields including client ID,
    correlation ID, BUY/SELL transaction type, exchange segment, product type,
    order type, validity, security ID and quantity. LIMIT orders use price;
    stop orders use triggerPrice. See official Dhan V2 order documentation.
    """

    def map(
        self,
        instruction: BoundExecutionInstruction,
        *,
        dhan_client_id: str,
        correlation_id: Optional[str] = None,
        disclosed_quantity: int = 0,
        after_market_order: bool = False,
        amo_time: str = "",
        bo_profit_value: float = 0.0,
        bo_stop_loss_value: float = 0.0,
    ) -> DhanOrderPayload:

        if not dhan_client_id:
            raise ValueError("dhan_client_id_required")

        if not instruction.security_id:
            raise ValueError("security_id_required")

        if instruction.exchange_segment not in _DHAN_SEGMENTS:
            raise ValueError("unsupported_dhan_exchange_segment")

        if instruction.product_type not in _DHAN_PRODUCTS:
            raise ValueError("unsupported_dhan_product_type")

        if instruction.validity not in _DHAN_VALIDITY:
            raise ValueError("unsupported_dhan_validity")

        if instruction.quantity <= 0:
            raise ValueError("dhan_quantity_must_be_positive")

        if disclosed_quantity < 0 or disclosed_quantity > instruction.quantity:
            raise ValueError("invalid_disclosed_quantity")

        # Chunk 53/55 currently exposes MARKET and LIMIT. Keep mapper narrow:
        # unsupported stop semantics must be introduced deliberately later.
        order_type = instruction.order_type.value
        if order_type not in {"MARKET", "LIMIT"}:
            raise ValueError("unsupported_dhan_order_type")

        price = 0.0
        if order_type == "LIMIT":
            if instruction.limit_price is None or instruction.limit_price <= 0:
                raise ValueError("dhan_limit_price_required")
            price = float(instruction.limit_price)

        if correlation_id is None:
            # The internal intent ID may be longer than Dhan's 30-character
            # correlationId limit. Generate a deterministic, compact, valid
            # correlation value rather than silently truncating it.
            correlation = "CTE-" + hashlib.sha256(
                instruction.intent_id.encode("utf-8")
            ).hexdigest()[:24]
        else:
            correlation = correlation_id
            if len(correlation) > 30:
                raise ValueError("dhan_correlation_id_too_long")

        # Dhan correlationId is constrained to a maximum of 30 characters and
        # this mapper permits only alphanumeric characters plus space, "_" and "-".
        allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 _-")
        if any(ch not in allowed for ch in correlation):
            raise ValueError("dhan_correlation_id_invalid")

        txn = instruction.action.value
        if txn not in {"BUY", "SELL"}:
            raise ValueError("unsupported_dhan_transaction_type")

        return DhanOrderPayload(
            dhanClientId=dhan_client_id,
            correlationId=correlation,
            transactionType=txn,
            exchangeSegment=instruction.exchange_segment,
            productType=instruction.product_type,
            orderType=order_type,
            validity=instruction.validity,
            securityId=instruction.security_id,
            quantity=instruction.quantity,
            disclosedQuantity=disclosed_quantity,
            price=price,
            triggerPrice=0.0,
            afterMarketOrder=after_market_order,
            amoTime=amo_time,
            boProfitValue=bo_profit_value,
            boStopLossValue=bo_stop_loss_value,
        )
