from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock
from time import monotonic
from typing import Dict


@dataclass(frozen=True)
class RuntimeMetricsSnapshot:
    cycles_total: int
    cycle_failures_total: int
    last_cycle_duration_seconds: float | None
    readiness_changes_total: int
    dependency_failures_total: int
    dependency_recoveries_total: int
    health_refreshes_total: int


@dataclass
class RuntimeMetrics:
    """In-process operational metrics; deliberately independent of trading decisions."""

    _lock: Lock = field(default_factory=Lock, init=False, repr=False)
    _cycles_total: int = 0
    _cycle_failures_total: int = 0
    _last_cycle_duration_seconds: float | None = None
    _readiness_changes_total: int = 0
    _dependency_failures_total: int = 0
    _dependency_recoveries_total: int = 0
    _health_refreshes_total: int = 0

    def cycle_started(self) -> float:
        return monotonic()

    def cycle_completed(self, started_at: float) -> None:
        duration = max(0.0, monotonic() - started_at)
        with self._lock:
            self._cycles_total += 1
            self._last_cycle_duration_seconds = duration

    def cycle_failed(self, started_at: float) -> None:
        duration = max(0.0, monotonic() - started_at)
        with self._lock:
            self._cycles_total += 1
            self._cycle_failures_total += 1
            self._last_cycle_duration_seconds = duration

    def readiness_changed(self) -> None:
        with self._lock:
            self._readiness_changes_total += 1

    def dependency_failed(self) -> None:
        with self._lock:
            self._dependency_failures_total += 1

    def dependency_recovered(self) -> None:
        with self._lock:
            self._dependency_recoveries_total += 1

    def health_refreshed(self) -> None:
        with self._lock:
            self._health_refreshes_total += 1

    def snapshot(self) -> RuntimeMetricsSnapshot:
        with self._lock:
            return RuntimeMetricsSnapshot(
                cycles_total=self._cycles_total,
                cycle_failures_total=self._cycle_failures_total,
                last_cycle_duration_seconds=self._last_cycle_duration_seconds,
                readiness_changes_total=self._readiness_changes_total,
                dependency_failures_total=self._dependency_failures_total,
                dependency_recoveries_total=self._dependency_recoveries_total,
                health_refreshes_total=self._health_refreshes_total,
            )


__all__ = ["RuntimeMetrics", "RuntimeMetricsSnapshot"]
