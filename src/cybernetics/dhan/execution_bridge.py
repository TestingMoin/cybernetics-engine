from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import hashlib

from cybernetics.brokers.interface import BrokerOrderRequest, BrokerOrderResult
from cybernetics.dhan.payload import DhanOrderPayload, DhanOrderPayloadMapper
from cybernetics.dhan.submission import (
    DhanExecutionPolicy,
    DhanOrderSubmissionAdapter,
    DhanSubmissionState,
)
from cybernetics.execution.binding import BoundExecutionInstruction


@dataclass(frozen=True)
class DhanExecutionBridge:
    """
    Canonical bridge from the broker-neutral execution layer to the existing
    Dhan V2 submission boundary.

    This object performs no automatic retries and does not change the supplied
    DhanExecutionPolicy. The existing DhanOrderSubmissionAdapter remains the
    final mutation safety boundary.
    """

    client_id: str
    mapper: DhanOrderPayloadMapper
    submission: DhanOrderSubmissionAdapter

    def payload_from_instruction(
        self,
        instruction: BoundExecutionInstruction,
        *,
        correlation_id: str | None = None,
        disclosed_quantity: int = 0,
    ) -> DhanOrderPayload:
        return self.mapper.map(
            instruction,
            dhan_client_id=self.client_id,
            correlation_id=correlation_id,
            disclosed_quantity=disclosed_quantity,
        )

    def submit_instruction(
        self,
        instruction: BoundExecutionInstruction,
        *,
        correlation_id: str | None = None,
        disclosed_quantity: int = 0,
    ):
        payload = self.payload_from_instruction(
            instruction,
            correlation_id=correlation_id,
            disclosed_quantity=disclosed_quantity,
        )
        return self.submission.submit(payload)

    def submit_broker_request(
        self,
        request: BrokerOrderRequest,
        *,
        security_id: str,
    ) -> BrokerOrderResult:
        if not security_id:
            return BrokerOrderResult(
                broker="DHAN_V2",
                accepted=False,
                broker_order_id=None,
                status="BLOCKED",
                message="security_id_required",
            )

        from cybernetics.dhan.payload import DhanOrderPayload

        correlation = "CTE-" + hashlib.sha256(
            f"{request.symbol}|{request.side}|{request.quantity}|{request.order_type}|{request.exchange_segment}|{security_id}".encode()
        ).hexdigest()[:24]
        payload = DhanOrderPayload(
            dhanClientId=self.client_id,
            correlationId=correlation,
            transactionType=request.side.upper(),
            exchangeSegment=request.exchange_segment,
            productType=request.product_type,
            orderType=request.order_type.upper(),
            validity="DAY",
            securityId=security_id,
            quantity=request.quantity,
            disclosedQuantity=0,
            price=0.0 if request.limit_price is None else request.limit_price,
            triggerPrice=0.0 if request.stop_price is None else request.stop_price,
            afterMarketOrder=False,
            amoTime="",
            boProfitValue=0.0,
            boStopLossValue=0.0,
        )

        result = self.submission.submit(payload)

        if result.state is DhanSubmissionState.SUBMITTED:
            return BrokerOrderResult(
                broker="DHAN_V2",
                accepted=True,
                broker_order_id=result.broker_order_id,
                status=result.broker_status or result.state.value,
                message=result.reason,
            )

        return BrokerOrderResult(
            broker="DHAN_V2",
            accepted=False,
            broker_order_id=result.broker_order_id,
            status=result.state.value,
            message=result.reason,
        )


def build_dhan_execution_bridge(
    *,
    client_id: str,
    transport: Any,
    access_token_provider: Any,
    engine_running: bool = False,
    live_authorized: bool = False,
    emergency_stop: bool = True,
    order_submission_enabled: bool = False,
) -> DhanExecutionBridge:
    if not client_id:
        raise ValueError("dhan_client_id_required")

    policy = DhanExecutionPolicy(
        engine_running=engine_running,
        live_authorized=live_authorized,
        emergency_stop=emergency_stop,
        order_submission_enabled=order_submission_enabled,
    )

    submission = DhanOrderSubmissionAdapter(
        transport=transport,
        access_token_provider=access_token_provider,
        policy=policy,
    )

    return DhanExecutionBridge(
        client_id=client_id,
        mapper=DhanOrderPayloadMapper(),
        submission=submission,
    )
