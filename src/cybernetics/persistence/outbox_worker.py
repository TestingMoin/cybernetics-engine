from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Iterable, Mapping, Protocol


class OutboxState(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class OutboxItem:
    event_id: str
    fill_id: str
    order_id: str
    trade_id: str
    payload: Mapping[str, Any]
    attempts: int


class OutboxRepository(Protocol):
    def claim_outbox_batch(self, limit: int = 100) -> Iterable[OutboxItem]: ...
    def complete_outbox(self, event_id: str) -> bool: ...
    def fail_outbox(self, event_id: str, error: str) -> bool: ...
    def recover_stale_processing(self, max_age_seconds: int) -> int: ...
    def pending_count(self) -> int: ...


@dataclass(frozen=True)
class DispatchResult:
    event_id: str
    status: str
    attempts: int
    error: str | None = None


@dataclass(frozen=True)
class WorkerConfig:
    batch_size: int = 100
    max_attempts: int = 5
    stale_after_seconds: int = 300

    def __post_init__(self):
        if self.batch_size <= 0:
            raise ValueError("batch_size_must_be_positive")
        if self.max_attempts <= 0:
            raise ValueError("max_attempts_must_be_positive")
        if self.stale_after_seconds <= 0:
            raise ValueError("stale_after_seconds_must_be_positive")


class DurableOutboxWorker:
    """
    Deterministic at-least-once outbox worker boundary.

    Handler side effects must themselves be idempotent. A successful handler is
    followed by durable COMPLETED state. A handler failure is durably FAILED
    after max attempts; otherwise it remains eligible for retry by returning
    through the repository's pending/recovery mechanics.
    """

    def __init__(self, repo: OutboxRepository, config: WorkerConfig | None = None):
        self.repo = repo
        self.config = config or WorkerConfig()

    def recover_stale(self) -> int:
        return self.repo.recover_stale_processing(
            self.config.stale_after_seconds
        )

    def run_once(
        self,
        handler: Callable[[OutboxItem], None],
    ) -> list[DispatchResult]:
        results: list[DispatchResult] = []
        for item in self.repo.claim_outbox_batch(self.config.batch_size):
            if item.attempts >= self.config.max_attempts:
                self.repo.fail_outbox(
                    item.event_id, "max_attempts_exceeded_before_dispatch"
                )
                results.append(
                    DispatchResult(
                        item.event_id, "FAILED", item.attempts,
                        "max_attempts_exceeded_before_dispatch"
                    )
                )
                continue

            try:
                handler(item)
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
                if item.attempts >= self.config.max_attempts:
                    self.repo.fail_outbox(item.event_id, error)
                    status = "FAILED"
                else:
                    # The repository can map FAILED to a retryable state in a
                    # later transaction according to its persistence policy.
                    self.repo.fail_outbox(item.event_id, error)
                    status = "RETRYABLE_FAILURE"
                results.append(
                    DispatchResult(item.event_id, status, item.attempts, error)
                )
                continue

            if not self.repo.complete_outbox(item.event_id):
                results.append(
                    DispatchResult(
                        item.event_id, "COMPLETION_UNKNOWN", item.attempts,
                        "outbox_completion_not_confirmed"
                    )
                )
                continue

            results.append(
                DispatchResult(item.event_id, "COMPLETED", item.attempts)
            )
        return results
