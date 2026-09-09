from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable, Optional

@dataclass(frozen=True)
class DhanOrderRequest:
    client_order_key: str
    dhan_client_id: str
    security_id: str
    transaction_type: str
    exchange_segment: str
    product_type: str
    order_type: str
    quantity: int
    validity: str = "DAY"
    price: Optional[float] = None
    trigger_price: Optional[float] = None
    disclosed_quantity: Optional[int] = None
    after_market_order: bool = False
    amo_time: Optional[str] = None

@dataclass(frozen=True)
class DhanOrderResponse:
    accepted: bool
    broker_order_id: Optional[str]
    order_status: str
    message: str
    raw: dict[str, Any]

class DhanApiError(RuntimeError):
    pass

class DhanV2OrderAdapter:
    """
    Dhan V2 order adapter boundary.

    The transport is injected. The adapter itself is deterministic and testable,
    while network/authentication lifecycle remains outside the order mapper.
    """
    BASE_URL = "https://api.dhan.co/v2"

    def __init__(self, transport: Callable[..., Any], access_token: str):
        if not access_token:
            raise ValueError("access_token_required")
        self._transport = transport
        self._access_token = access_token

    @staticmethod
    def _body(req: DhanOrderRequest) -> dict[str, Any]:
        body = {
            "dhanClientId": req.dhan_client_id,
            "correlationId": req.client_order_key,
            "transactionType": req.transaction_type,
            "exchangeSegment": req.exchange_segment,
            "productType": req.product_type,
            "orderType": req.order_type,
            "validity": req.validity,
            "securityId": req.security_id,
            "quantity": str(req.quantity),
            "disclosedQuantity": "" if req.disclosed_quantity is None else str(req.disclosed_quantity),
            "price": "" if req.price is None else req.price,
            "triggerPrice": "" if req.trigger_price is None else req.trigger_price,
            "afterMarketOrder": req.after_market_order,
            "amoTime": "" if req.amo_time is None else req.amo_time,
        }
        return body

    def place_order(self, req: DhanOrderRequest) -> DhanOrderResponse:
        response = self._transport(
            "POST",
            f"{self.BASE_URL}/orders",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "access-token": self._access_token,
            },
            json=self._body(req),
        )
        return self._normalize(response)

    def get_order(self, order_id: str) -> DhanOrderResponse:
        response = self._transport(
            "GET",
            f"{self.BASE_URL}/orders/{order_id}",
            headers={"Accept": "application/json", "access-token": self._access_token},
        )
        return self._normalize(response)

    def get_order_by_correlation_id(self, correlation_id: str) -> DhanOrderResponse:
        response = self._transport(
            "GET",
            f"{self.BASE_URL}/orders/external/{correlation_id}",
            headers={"Accept": "application/json", "access-token": self._access_token},
        )
        return self._normalize(response)

    def cancel_order(self, order_id: str) -> DhanOrderResponse:
        response = self._transport(
            "DELETE",
            f"{self.BASE_URL}/orders/{order_id}",
            headers={"Accept": "application/json", "access-token": self._access_token},
        )
        return self._normalize(response)

    @staticmethod
    def _normalize(response: Any) -> DhanOrderResponse:
        if not isinstance(response, dict):
            raise DhanApiError("invalid_response_type")

        status = str(response.get("orderStatus") or response.get("status") or "UNKNOWN").upper()
        broker_id = response.get("orderId")
        message = str(response.get("errorMessage") or response.get("message") or "")
        accepted = status in {"TRANSIT","PENDING","PART_TRADED","TRADED","TRIGGERED","MODIFIED","OPEN"}

        if response.get("errorCode") or response.get("errorType"):
            accepted = False

        return DhanOrderResponse(
            accepted=accepted,
            broker_order_id=str(broker_id) if broker_id is not None else None,
            order_status=status,
            message=message,
            raw=response,
        )
