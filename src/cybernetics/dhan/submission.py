from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Protocol
from urllib.error import URLError

from cybernetics.integration.dhan_runtime import DhanTransportError

from cybernetics.dhan.payload import DhanOrderPayload


class DhanSubmissionState(str, Enum):
    SUBMITTED = "SUBMITTED"
    REJECTED = "REJECTED"
    UNKNOWN = "UNKNOWN"
    BLOCKED = "BLOCKED"


class DhanTransport(Protocol):
    def post_json(
        self,
        *,
        path: str,
        headers: Mapping[str, str],
        json_body: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        ...


@dataclass(frozen=True)
class DhanExecutionPolicy:
    """
    Explicit live-submission controls.

    Live order submission requires every independent condition to pass.
    """
    engine_running: bool = False
    live_authorized: bool = False
    emergency_stop: bool = True
    order_submission_enabled: bool = False


@dataclass(frozen=True)
class DhanSubmissionResult:
    state: DhanSubmissionState
    reason: str
    endpoint: str
    correlation_id: str
    broker_order_id: str | None = None
    broker_status: str | None = None
    raw_response: dict[str, Any] | None = None


class DhanOrderSubmissionAdapter:
    """
    Final Dhan REST submission boundary.

    This adapter uses an injected transport so production networking remains
    centralized in the existing Dhan REST transport/rate-limit layer.

    Critical behavior:
    - live submission is OFF by default
    - emergency stop blocks submission
    - engine must be running
    - live authorization and explicit order-submission enable are both required
    - a non-idempotent POST is never blindly retried
    - transport uncertainty returns UNKNOWN rather than retrying
    """

    ENDPOINT = "/v2/orders"

    def __init__(
        self,
        *,
        transport: DhanTransport,
        access_token_provider,
        policy: DhanExecutionPolicy,
    ):
        self.transport = transport
        self.access_token_provider = access_token_provider
        self.policy = policy

    def submit(self, payload: DhanOrderPayload) -> DhanSubmissionResult:
        correlation = payload.correlationId

        if self.policy.emergency_stop:
            return DhanSubmissionResult(
                DhanSubmissionState.BLOCKED,
                "emergency_stop_active",
                self.ENDPOINT,
                correlation,
            )

        if not self.policy.engine_running:
            return DhanSubmissionResult(
                DhanSubmissionState.BLOCKED,
                "engine_not_running",
                self.ENDPOINT,
                correlation,
            )

        if not self.policy.live_authorized:
            return DhanSubmissionResult(
                DhanSubmissionState.BLOCKED,
                "live_authorization_missing",
                self.ENDPOINT,
                correlation,
            )

        if not self.policy.order_submission_enabled:
            return DhanSubmissionResult(
                DhanSubmissionState.BLOCKED,
                "order_submission_disabled",
                self.ENDPOINT,
                correlation,
            )

        token = self.access_token_provider()
        if not token:
            return DhanSubmissionResult(
                DhanSubmissionState.REJECTED,
                "access_token_unavailable",
                self.ENDPOINT,
                correlation,
            )

        headers = {
            "Content-Type": "application/json",
            "access-token": token,
        }

        try:
            response = dict(
                self.transport.post_json(
                    path=self.ENDPOINT,
                    headers=headers,
                    json_body=payload.as_dict(),
                )
            )
        except TimeoutError:
            # POST order placement is non-idempotent. Never blindly retry.
            return DhanSubmissionResult(
                DhanSubmissionState.UNKNOWN,
                "transport_timeout_no_retry",
                self.ENDPOINT,
                correlation,
            )
        except ConnectionError:
            return DhanSubmissionResult(
                DhanSubmissionState.UNKNOWN,
                "transport_connection_uncertain_no_retry",
                self.ENDPOINT,
                correlation,
            )
        except DhanTransportError as exc:
            cause = exc.__cause__
            if isinstance(cause, (TimeoutError, ConnectionError, URLError, OSError)):
                return DhanSubmissionResult(
                    DhanSubmissionState.UNKNOWN,
                    "transport_uncertain_no_retry",
                    self.ENDPOINT,
                    correlation,
                )
            return DhanSubmissionResult(
                DhanSubmissionState.REJECTED,
                f"transport_error:{type(exc).__name__}",
                self.ENDPOINT,
                correlation,
            )
        except Exception as exc:
            return DhanSubmissionResult(
                DhanSubmissionState.REJECTED,
                f"transport_error:{type(exc).__name__}",
                self.ENDPOINT,
                correlation,
            )

        order_id = response.get("orderId")
        status = response.get("orderStatus")

        if not order_id:
            return DhanSubmissionResult(
                DhanSubmissionState.UNKNOWN,
                "response_missing_order_id",
                self.ENDPOINT,
                correlation,
                broker_status=str(status) if status is not None else None,
                raw_response=response,
            )

        if str(status).upper() == "REJECTED":
            return DhanSubmissionResult(
                DhanSubmissionState.REJECTED,
                "broker_rejected_order",
                self.ENDPOINT,
                correlation,
                broker_order_id=str(order_id),
                broker_status=str(status),
                raw_response=response,
            )

        return DhanSubmissionResult(
            DhanSubmissionState.SUBMITTED,
            "broker_order_accepted",
            self.ENDPOINT,
            correlation,
            broker_order_id=str(order_id),
            broker_status=str(status) if status is not None else None,
            raw_response=response,
        )
