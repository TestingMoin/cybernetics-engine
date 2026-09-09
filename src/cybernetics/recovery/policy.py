from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RecoveryAction(str, Enum):
    RESOLVE = "RESOLVE"
    BLOCK_NEW_TRADES = "BLOCK_NEW_TRADES"
    REQUIRE_HUMAN_REVIEW = "REQUIRE_HUMAN_REVIEW"


@dataclass(frozen=True)
class RecoveryDecision:
    action: RecoveryAction
    reason: str


class RecoveryPolicy:
    """Maps reconciliation outcomes to conservative recovery decisions."""

    def decide(self, *, consistent: bool, broker_order_found: bool) -> RecoveryDecision:
        if consistent and broker_order_found:
            return RecoveryDecision(
                RecoveryAction.RESOLVE,
                "broker_order_and_position_state_consistent",
            )
        if not broker_order_found:
            return RecoveryDecision(
                RecoveryAction.REQUIRE_HUMAN_REVIEW,
                "broker_order_missing_or_unverifiable",
            )
        return RecoveryDecision(
            RecoveryAction.BLOCK_NEW_TRADES,
            "state_mismatch_requires_reconciliation",
        )
