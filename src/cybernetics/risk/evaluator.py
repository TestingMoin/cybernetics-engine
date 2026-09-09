from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Any

from .handoff import StrategyRiskRequest, RiskAction

class RiskDecision(str, Enum):
    APPROVED="APPROVED"
    REJECTED="REJECTED"

@dataclass(frozen=True)
class RiskLimits:
    max_daily_loss: float = 0.0
    max_open_exposure: float = 0.0
    max_trade_risk: float = 0.0
    margin_buffer: float = 0.0

@dataclass(frozen=True)
class RiskPortfolioState:
    realized_pnl_today: float = 0.0
    open_exposure: float = 0.0
    used_margin: float = 0.0
    available_margin: float = 0.0
    emergency_stop: bool = False
    live_authorized: bool = False

@dataclass(frozen=True)
class RiskEvaluation:
    decision: RiskDecision
    reason: str
    request_id: str
    calculated_trade_risk: Optional[float] = None
    projected_exposure: Optional[float] = None
    projected_margin: Optional[float] = None

class RiskRequestEvaluator:
    """
    Deterministic evaluation boundary for StrategyRiskRequest.

    This layer evaluates risk controls but deliberately does not submit orders.
    Quantity must be supplied by the downstream sizing policy only after the
    request passes the required validations. This chunk therefore requires a
    caller-provided proposed quantity/notional for evaluation rather than
    allowing strategy code to determine it.
    """
    def __init__(self, limits: RiskLimits):
        self.limits = limits

    def evaluate(
        self,
        request: StrategyRiskRequest,
        *,
        portfolio: RiskPortfolioState,
        proposed_quantity: int,
        contract_multiplier: float,
        entry_price: Optional[float] = None,
    ) -> RiskEvaluation:
        if portfolio.emergency_stop:
            return RiskEvaluation(RiskDecision.REJECTED, "emergency_stop_active", request.request_id)

        if not portfolio.live_authorized and request.metadata.get("execution_mode") == "live":
            return RiskEvaluation(RiskDecision.REJECTED, "live_authorization_missing", request.request_id)

        if proposed_quantity <= 0:
            return RiskEvaluation(RiskDecision.REJECTED, "proposed_quantity_invalid", request.request_id)

        if contract_multiplier <= 0:
            return RiskEvaluation(RiskDecision.REJECTED, "contract_multiplier_invalid", request.request_id)

        price = entry_price if entry_price is not None else request.entry_reference_price
        if request.action in {RiskAction.ENTER_LONG, RiskAction.ENTER_SHORT} and (price is None or price <= 0):
            return RiskEvaluation(RiskDecision.REJECTED, "entry_price_required", request.request_id)

        projected_exposure = portfolio.open_exposure
        projected_margin = portfolio.used_margin

        if request.action in {RiskAction.ENTER_LONG, RiskAction.ENTER_SHORT}:
            notional = proposed_quantity * contract_multiplier * price
            projected_exposure += abs(notional)

            if self.limits.max_open_exposure > 0 and projected_exposure > self.limits.max_open_exposure:
                return RiskEvaluation(
                    RiskDecision.REJECTED,
                    "max_open_exposure_exceeded",
                    request.request_id,
                    projected_exposure=projected_exposure,
                )

            # This is a guard/consistency calculation only. Exact margin policy
            # remains downstream and broker/instrument specific.
            projected_margin += abs(notional)

            if portfolio.available_margin > 0 and projected_margin > portfolio.available_margin + portfolio.used_margin:
                return RiskEvaluation(
                    RiskDecision.REJECTED,
                    "margin_capacity_exceeded",
                    request.request_id,
                    projected_exposure=projected_exposure,
                    projected_margin=projected_margin,
                )

            if (
                request.stop_reference_price is not None
                and request.stop_reference_price > 0
            ):
                calculated_trade_risk = (
                    abs(price - request.stop_reference_price)
                    * proposed_quantity
                    * contract_multiplier
                )
                if (
                    self.limits.max_trade_risk > 0
                    and calculated_trade_risk > self.limits.max_trade_risk
                ):
                    return RiskEvaluation(
                        RiskDecision.REJECTED,
                        "max_trade_risk_exceeded",
                        request.request_id,
                        calculated_trade_risk=calculated_trade_risk,
                        projected_exposure=projected_exposure,
                        projected_margin=projected_margin,
                    )
            else:
                calculated_trade_risk = None

            if (
                self.limits.max_daily_loss > 0
                and portfolio.realized_pnl_today <= -self.limits.max_daily_loss
            ):
                return RiskEvaluation(
                    RiskDecision.REJECTED,
                    "daily_loss_limit_reached",
                    request.request_id,
                    projected_exposure=projected_exposure,
                    projected_margin=projected_margin,
                )

            return RiskEvaluation(
                RiskDecision.APPROVED,
                "risk_checks_passed",
                request.request_id,
                calculated_trade_risk=calculated_trade_risk,
                projected_exposure=projected_exposure,
                projected_margin=projected_margin,
            )

        # Exit requests are safety-relevant and should not be rejected merely
        # because entry-specific exposure checks do not apply.
        if request.action in {RiskAction.EXIT_LONG, RiskAction.EXIT_SHORT}:
            return RiskEvaluation(
                RiskDecision.APPROVED,
                "exit_risk_checks_passed",
                request.request_id,
                projected_exposure=projected_exposure,
                projected_margin=projected_margin,
            )

        return RiskEvaluation(
            RiskDecision.REJECTED, "non_executable_risk_action", request.request_id
        )
