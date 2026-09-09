from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Callable, Optional

class SignalLifecycleState(str, Enum):
    OBSERVED="OBSERVED"
    ACTIVE="ACTIVE"
    INVALIDATED="INVALIDATED"
    EXPIRED="EXPIRED"
    SUPERSEDED="SUPERSEDED"

class InvalidationReason(str, Enum):
    EXPLICIT="EXPLICIT"
    OPPOSITE_SIGNAL="OPPOSITE_SIGNAL"
    MARKET_STATE_INVALID="MARKET_STATE_INVALID"
    DATA_STALE="DATA_STALE"
    MANUAL="MANUAL"

@dataclass(frozen=True)
class SignalEvaluation:
    signal_id: str
    state: SignalLifecycleState
    valid: bool
    reason: str

@dataclass
class _SignalRuntime:
    signal_id: str
    created_at: datetime
    expires_at: Optional[datetime]
    state: SignalLifecycleState
    last_evaluated_at: Optional[datetime] = None
    invalidation_reason: Optional[InvalidationReason] = None
    superseded_by: Optional[str] = None
    revision: int = 1

class SignalLifecycleManager:
    """
    Owns the temporal lifecycle of registered signals.

    This component does not create orders and does not alter strategy decisions.
    A signal can only move forward in lifecycle; a terminal state is never silently
    reactivated.
    """
    TERMINAL={
        SignalLifecycleState.INVALIDATED,
        SignalLifecycleState.EXPIRED,
        SignalLifecycleState.SUPERSEDED,
    }

    def __init__(self, now: Optional[Callable[[], datetime]]=None):
        self._now=now or (lambda: datetime.now(timezone.utc))
        self._signals: dict[str,_SignalRuntime]={}

    def register(self, signal_id: str, *,
                 created_at: Optional[datetime]=None,
                 ttl: Optional[timedelta]=None,
                 initial_state: SignalLifecycleState=SignalLifecycleState.OBSERVED) -> SignalEvaluation:
        if not signal_id:
            raise ValueError("signal_id_required")
        if signal_id in self._signals:
            raise ValueError("signal_already_registered")
        if ttl is not None and ttl.total_seconds() <= 0:
            raise ValueError("signal_ttl_must_be_positive")

        created=created_at or self._now()
        self._require_aware(created)
        expires=created+ttl if ttl is not None else None
        self._signals[signal_id]=_SignalRuntime(
            signal_id,created,expires,initial_state
        )
        return self.evaluate(signal_id)

    def activate(self, signal_id: str) -> SignalEvaluation:
        r=self._get(signal_id)
        self._check_expiry(r)
        if r.state in self.TERMINAL:
            return self.evaluate(signal_id)
        if r.state==SignalLifecycleState.OBSERVED:
            r.state=SignalLifecycleState.ACTIVE
            r.revision+=1
        return self.evaluate(signal_id)

    def evaluate(self, signal_id: str,
                 at: Optional[datetime]=None) -> SignalEvaluation:
        r=self._get(signal_id)
        now=at or self._now()
        self._require_aware(now)
        if r.expires_at is not None and now >= r.expires_at and r.state not in self.TERMINAL:
            r.state=SignalLifecycleState.EXPIRED
            r.invalidation_reason=None
            r.revision+=1
        r.last_evaluated_at=now
        return SignalEvaluation(
            r.signal_id,
            r.state,
            r.state in {SignalLifecycleState.OBSERVED,SignalLifecycleState.ACTIVE},
            self._reason(r),
        )

    def invalidate(self, signal_id: str,
                   reason: InvalidationReason) -> SignalEvaluation:
        r=self._get(signal_id)
        if r.state in self.TERMINAL:
            return self.evaluate(signal_id)
        r.state=SignalLifecycleState.INVALIDATED
        r.invalidation_reason=reason
        r.revision+=1
        return self.evaluate(signal_id)

    def supersede(self, old_signal_id: str, new_signal_id: str) -> SignalEvaluation:
        if old_signal_id == new_signal_id:
            raise ValueError("cannot_supersede_with_same_signal")
        old=self._get(old_signal_id)
        if new_signal_id not in self._signals:
            raise KeyError("superseding_signal_not_registered")
        if old.state in self.TERMINAL:
            return self.evaluate(old_signal_id)
        old.state=SignalLifecycleState.SUPERSEDED
        old.superseded_by=new_signal_id
        old.revision+=1
        return self.evaluate(old_signal_id)

    def state(self, signal_id: str)->SignalLifecycleState:
        return self.evaluate(signal_id).state

    def revision(self, signal_id: str)->int:
        return self._get(signal_id).revision

    def metadata(self, signal_id: str)->dict:
        r=self._get(signal_id)
        return {
            "signal_id":r.signal_id,
            "created_at":r.created_at,
            "expires_at":r.expires_at,
            "state":r.state,
            "last_evaluated_at":r.last_evaluated_at,
            "invalidation_reason":r.invalidation_reason,
            "superseded_by":r.superseded_by,
            "revision":r.revision,
        }

    def _check_expiry(self,r:_SignalRuntime):
        if r.expires_at is not None and self._now() >= r.expires_at and r.state not in self.TERMINAL:
            r.state=SignalLifecycleState.EXPIRED
            r.revision+=1

    def _reason(self,r:_SignalRuntime)->str:
        if r.state==SignalLifecycleState.SUPERSEDED:
            return f"superseded_by:{r.superseded_by}"
        if r.state==SignalLifecycleState.INVALIDATED:
            return f"invalidated:{r.invalidation_reason.value if r.invalidation_reason else 'UNKNOWN'}"
        return r.state.value.lower()

    def _get(self,sid):
        try:return self._signals[sid]
        except KeyError:raise KeyError("signal_not_found")

    @staticmethod
    def _require_aware(value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("signal_timestamp_must_be_timezone_aware")
