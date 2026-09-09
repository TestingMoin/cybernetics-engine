from __future__ import annotations
from enum import Enum
from .unknown_resolver import ResolutionState, UnknownOrderResolver

class RetryDecision(str, Enum):
    ALLOW_NEW_SUBMISSION = "ALLOW_NEW_SUBMISSION"
    BLOCK = "BLOCK"

class SafeRetryGuard:
    """
    A NEW submission is allowed only after UNKNOWN is positively resolved as
    rejected/cancelled/expired. UNKNOWN or ambiguous outcomes remain blocked.
    """
    def __init__(self, resolver: UnknownOrderResolver):
        self._resolver = resolver

    def decide(self, client_order_key: str) -> RetryDecision:
        result = self._resolver.resolve(client_order_key)
        if result.state == ResolutionState.RESOLVED_REJECTED:
            return RetryDecision.ALLOW_NEW_SUBMISSION
        return RetryDecision.BLOCK
