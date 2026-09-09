from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import signal
import threading
from typing import Callable, Optional, Protocol

from .composition import RuntimeSignals, RuntimeSnapshot, RuntimeStateComposer
from .state import EngineMode
from .metrics import RuntimeMetrics


class ApplicationLifecycle(str, Enum):
    CREATED = "CREATED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class RuntimeConfig:
    """Configuration for the canonical process entrypoint.

    The entrypoint is intentionally fail-closed: no broker connection, live
    authorization, order submission, or database mutation is created by
    default. Those are injected by a later production composition layer.
    """

    service_name: str = "cybernetics-engine"
    poll_interval_seconds: float = 1.0

    def __post_init__(self) -> None:
        if not self.service_name:
            raise ValueError("service_name_required")
        if self.poll_interval_seconds <= 0:
            raise ValueError("poll_interval_seconds_must_be_positive")


class FailClosedBootstrapSignals:
    """Safe bootstrap signal source used until production dependencies exist."""

    def engine_mode(self):
        return EngineMode.STOPPED

    def control_state(self):
        from .state import ControlState
        return ControlState.STOP_NEW_TRADES

    def persistence_ready(self):
        return False

    def recovery_clear(self):
        return False

    def orders_reconciled(self):
        return False

    def positions_reconciled(self):
        return False

    def market_data_ready(self):
        return False

    def scanner_health_ready(self):
        return False

    def watchdog_healthy(self):
        return False

    def live_authorization_valid(self):
        return False

    def broker_available(self):
        return False

    def emergency_state(self):
        from .state import EmergencyState
        return EmergencyState.CLEAR


class RuntimeAuditPort(Protocol):
    def lifecycle(self, state: str, *, previous: str | None = None): ...
    def readiness(self, *, engine_ready: bool, new_trades_allowed: bool, reason: str): ...


class RuntimeApplication:
    """Canonical lifecycle wrapper for the Cybernetics process.

    The class owns process lifecycle only. It deliberately does not embed
    trading, broker, or order logic. A production composition root can inject
    real ``RuntimeSignals`` and lifecycle hooks without changing the process
    entrypoint contract.
    """

    def __init__(
        self,
        *,
        config: RuntimeConfig | None = None,
        signals: RuntimeSignals | None = None,
        on_start: Optional[Callable[[], None]] = None,
        on_stop: Optional[Callable[[], None]] = None,
        on_refresh: Optional[Callable[[], None]] = None,
        audit: RuntimeAuditPort | None = None,
        metrics: RuntimeMetrics | None = None,
    ) -> None:
        self.config = config or RuntimeConfig()
        self.signals = signals or FailClosedBootstrapSignals()
        self.composer = RuntimeStateComposer(self.signals)
        self.on_start = on_start
        self.on_stop = on_stop
        self.on_refresh = on_refresh
        self.audit = audit
        self.metrics = metrics or RuntimeMetrics()
        self.lifecycle = ApplicationLifecycle.CREATED
        self._stop_event = threading.Event()
        self._last_snapshot: RuntimeSnapshot | None = None

    def _audit_lifecycle(self, previous: ApplicationLifecycle, current: ApplicationLifecycle) -> None:
        if self.audit is not None and previous is not current:
            self.audit.lifecycle(current.value, previous=previous.value)

    def _audit_snapshot(self, snapshot: RuntimeSnapshot) -> None:
        if self.audit is None:
            return
        previous = self._last_snapshot
        changed = previous is None or (
            previous.readiness.engine_ready != snapshot.readiness.engine_ready
            or previous.readiness.new_trades_allowed != snapshot.readiness.new_trades_allowed
        )
        if changed:
            self.metrics.readiness_changed()
            reason = ";".join(snapshot.readiness.reasons) if snapshot.readiness.reasons else "ready"
            self.audit.readiness(
                engine_ready=snapshot.readiness.engine_ready,
                new_trades_allowed=snapshot.readiness.new_trades_allowed,
                reason=reason,
            )

    def snapshot(self) -> RuntimeSnapshot:
        current = self.composer.snapshot()
        self._audit_snapshot(current)
        self._last_snapshot = current
        return current

    @property
    def last_snapshot(self) -> RuntimeSnapshot | None:
        return self._last_snapshot

    def start(self) -> RuntimeSnapshot:
        if self.lifecycle is not ApplicationLifecycle.CREATED:
            raise RuntimeError("application_not_created")
        previous = self.lifecycle
        self.lifecycle = ApplicationLifecycle.STARTING
        self._audit_lifecycle(previous, self.lifecycle)
        try:
            if self.on_start:
                self.on_start()
            # Evaluate readiness during startup, but do not equate engine
            # process liveness with trading readiness. The process may be
            # RUNNING while new-trade readiness remains false.
            startup_snapshot = self.snapshot()
            previous = self.lifecycle
            self.lifecycle = ApplicationLifecycle.RUNNING
            self._audit_lifecycle(previous, self.lifecycle)
            return startup_snapshot
        except Exception:
            previous = self.lifecycle
            self.lifecycle = ApplicationLifecycle.FAILED
            self._audit_lifecycle(previous, self.lifecycle)
            raise

    def refresh_snapshot(self) -> RuntimeSnapshot:
        """Refresh dependency health, then rebuild the canonical snapshot."""
        if self.lifecycle not in {ApplicationLifecycle.STARTING, ApplicationLifecycle.RUNNING}:
            raise RuntimeError("application_not_running_or_starting")
        if self.on_refresh:
            self.on_refresh()
        self.metrics.health_refreshed()
        return self.snapshot()

    def stop(self) -> None:
        if self.lifecycle in {
            ApplicationLifecycle.STOPPED,
            ApplicationLifecycle.CREATED,
        }:
            previous = self.lifecycle
            self.lifecycle = ApplicationLifecycle.STOPPED
            self._audit_lifecycle(previous, self.lifecycle)
            return
        previous = self.lifecycle
        self.lifecycle = ApplicationLifecycle.STOPPING
        self._audit_lifecycle(previous, self.lifecycle)
        try:
            if self.on_stop:
                self.on_stop()
        finally:
            self._stop_event.set()
            self.lifecycle = ApplicationLifecycle.STOPPED

    def wait(self) -> None:
        if self.lifecycle is not ApplicationLifecycle.RUNNING:
            raise RuntimeError("application_not_running")
        self._stop_event.wait(self.config.poll_interval_seconds)

    def run_cycle(self) -> RuntimeSnapshot:
        """Execute one supervisory cycle while the application is RUNNING.

        A cycle refreshes the canonical readiness snapshot and does not submit
        orders, mutate control state, or perform broker/database side effects
        itself. Concrete production dependencies remain behind injected signal
        providers.
        """
        if self.lifecycle is not ApplicationLifecycle.RUNNING:
            raise RuntimeError("application_not_running")
        started = self.metrics.cycle_started()
        try:
            snapshot = self.refresh_snapshot()
            self.metrics.cycle_completed(started)
            return snapshot
        except Exception:
            self.metrics.cycle_failed(started)
            raise

    def request_stop(self) -> None:
        self._stop_event.set()

    def run(self) -> int:
        self.start()
        try:
            while not self._stop_event.is_set():
                self.run_cycle()
                if not self._stop_event.is_set():
                    self.wait()
            return 0
        except KeyboardInterrupt:
            return 0
        except Exception:
            previous = self.lifecycle
            self.lifecycle = ApplicationLifecycle.FAILED
            self._audit_lifecycle(previous, self.lifecycle)
            raise
        finally:
            self.stop()


def install_signal_handlers(app: RuntimeApplication) -> None:
    """Install process-level stop handlers for SIGINT/SIGTERM."""

    def _handle(_signum: int, _frame: object) -> None:
        app.request_stop()

    signal.signal(signal.SIGINT, _handle)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _handle)
