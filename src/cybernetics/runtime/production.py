from __future__ import annotations

from dataclasses import dataclass

from cybernetics.config.settings import DeploymentConfig, TradingMode

from .application import RuntimeApplication, RuntimeConfig
from .dependencies import RuntimeDependencyBundle
from .state import ControlState, EmergencyState, EngineMode
from .persistence_recovery import PersistenceRecoveryRuntimeWiring
from .scanners import ScannerRuntimeWiring
from .watchdog import HealthRegistryWatchdogProbe
from .broker import BrokerRuntimeWiring
from .control_wiring import ControlRuntimeWiring
from .authorization_wiring import LiveAuthorizationRuntimeWiring
from .market_feed import MarketFeedRuntimeWiring
from .failure_handling import RuntimeDependencyFailureHandler
from cybernetics.db.staging import PostgreSQLStagingConfig
from .postgres import PostgreSQLRuntimeAdapter


@dataclass
class RuntimeDependencyState:
    """Runtime dependency-health values supplied by real adapters later.

    Defaults are deliberately unsafe.  A production composition must explicitly
    report readiness from each dependency instead of assuming availability.
    """

    engine_running: bool = False
    control_state: ControlState = ControlState.STOP_NEW_TRADES
    emergency_state: EmergencyState = EmergencyState.CLEAR
    persistence_ready: bool = False
    recovery_clear: bool = False
    orders_reconciled: bool = False
    positions_reconciled: bool = False
    market_data_ready: bool = False
    scanner_health_ready: bool = False
    watchdog_healthy: bool = False
    broker_available: bool = False
    live_authorization_valid: bool = False


class ProductionRuntimeSignals:
    """Canonical signal adapter for the runtime composition root.

    This object contains no broker I/O.  Concrete adapters update the supplied
    state after their own health/recovery checks.  LIVE authorization is kept as
    a separate runtime signal from engine state and control state.
    """

    def __init__(self, state: RuntimeDependencyState, config: DeploymentConfig):
        self.state = state
        self.config = config

    def engine_mode(self) -> EngineMode:
        return EngineMode.RUNNING if self.state.engine_running else EngineMode.STOPPED

    def control_state(self) -> ControlState:
        return self.state.control_state

    def emergency_state(self) -> EmergencyState:
        return self.state.emergency_state

    def persistence_ready(self) -> bool:
        return self.state.persistence_ready

    def recovery_clear(self) -> bool:
        return self.state.recovery_clear

    def orders_reconciled(self) -> bool:
        return self.state.orders_reconciled

    def positions_reconciled(self) -> bool:
        return self.state.positions_reconciled

    def market_data_ready(self) -> bool:
        return self.state.market_data_ready

    def scanner_health_ready(self) -> bool:
        return self.state.scanner_health_ready

    def watchdog_healthy(self) -> bool:
        return self.state.watchdog_healthy

    def broker_available(self) -> bool:
        return self.state.broker_available

    def live_authorization_valid(self) -> bool:
        return (
            self.config.trading_mode is TradingMode.LIVE
            and self.config.live_authorization_configured
            and self.state.live_authorization_valid
        )


class RuntimeDependencyHealthRefresher:
    """Re-evaluate injected runtime dependencies on every supervisory cycle.

    The refresher performs no dependency I/O of its own. Each injected wiring
    object owns its health/readiness probe. The refresher merely snapshots those
    results into the existing canonical RuntimeDependencyState so the runtime
    cannot continue using stale dependency booleans.
    """

    def __init__(
        self,
        *,
        state: RuntimeDependencyState,
        persistence_recovery: PersistenceRecoveryRuntimeWiring | None = None,
        market_feed_runtime: MarketFeedRuntimeWiring | None = None,
        scanner_runtime: ScannerRuntimeWiring | None = None,
        watchdog_runtime: HealthRegistryWatchdogProbe | None = None,
        broker_runtime: BrokerRuntimeWiring | None = None,
        control_runtime: ControlRuntimeWiring | None = None,
        authorization_runtime: LiveAuthorizationRuntimeWiring | None = None,
        dependencies: RuntimeDependencyBundle | None = None,
        config: DeploymentConfig | None = None,
        failure_handler: RuntimeDependencyFailureHandler | None = None,
        postgres_runtime: PostgreSQLRuntimeAdapter | None = None,
    ) -> None:
        self.state = state
        self.persistence_recovery = persistence_recovery
        self.market_feed_runtime = market_feed_runtime
        self.scanner_runtime = scanner_runtime
        self.watchdog_runtime = watchdog_runtime
        self.broker_runtime = broker_runtime
        self.control_runtime = control_runtime
        self.authorization_runtime = authorization_runtime
        self.dependencies = dependencies
        self.config = config
        self.postgres_runtime = postgres_runtime
        self.failure_handler = failure_handler or RuntimeDependencyFailureHandler(
            set_control_state=self._set_safe_control_state
        )

    def _set_safe_control_state(self, control_state: ControlState) -> None:
        self.state = _replace_state(self.state, control_state=control_state)

    def refresh(self) -> RuntimeDependencyState:
        state = self.state
        if self.dependencies is not None:
            state = self.dependencies.as_dependency_state(base_state=state)

        if self.market_feed_runtime is not None:
            state = _replace_state(state, market_data_ready=self.market_feed_runtime.market_data_ready())
        if self.scanner_runtime is not None:
            state = _replace_state(state, scanner_health_ready=self.scanner_runtime.scanner_health_ready())
        if self.watchdog_runtime is not None:
            state = _replace_state(state, watchdog_healthy=self.watchdog_runtime.watchdog_healthy())
        if self.broker_runtime is not None:
            state = _replace_state(state, broker_available=self.broker_runtime.broker_available())
        if self.control_runtime is not None:
            control_snapshot = self.control_runtime.snapshot()
            state = _replace_state(
                state,
                control_state=control_snapshot.control_state,
                emergency_state=control_snapshot.emergency_state,
            )
        if self.authorization_runtime is not None:
            state = _replace_state(
                state,
                live_authorization_valid=self.authorization_runtime.live_authorization_valid(),
            )
        if self.postgres_runtime is not None:
            state = _replace_state(
                state,
                persistence_ready=self.postgres_runtime.persistence_ready(),
                orders_reconciled=self.postgres_runtime.reconcile_orders(),
                positions_reconciled=self.postgres_runtime.reconcile_positions(),
            )
        if self.persistence_recovery is not None:
            bridge_state = self.persistence_recovery.runtime_readiness()
            state = _replace_state(
                state,
                persistence_ready=bridge_state["persistence_ready"],
                recovery_clear=bridge_state["recovery_clear"],
                orders_reconciled=bridge_state["orders_reconciled"],
                positions_reconciled=bridge_state["positions_reconciled"],
            )

        self.state = state

        dependency_readiness = {
            "persistence": state.persistence_ready,
            "recovery": state.recovery_clear,
            "market_data": state.market_data_ready,
            "scanners": state.scanner_health_ready,
            "watchdog": state.watchdog_healthy,
            "broker": state.broker_available,
        }
        self.failure_handler.evaluate(
            dependency_readiness,
            control_state=state.control_state,
            emergency_state=state.emergency_state,
        )
        # The failure handler may have requested a safe control state. Return
        # the post-action state so downstream signals cannot retain a stale
        # RUNNING control state for the same supervisory cycle.
        return self.state


def _replace_state(state: RuntimeDependencyState, **changes) -> RuntimeDependencyState:
    values = {
        "engine_running": state.engine_running,
        "control_state": state.control_state,
        "emergency_state": state.emergency_state,
        "persistence_ready": state.persistence_ready,
        "recovery_clear": state.recovery_clear,
        "orders_reconciled": state.orders_reconciled,
        "positions_reconciled": state.positions_reconciled,
        "market_data_ready": state.market_data_ready,
        "scanner_health_ready": state.scanner_health_ready,
        "watchdog_healthy": state.watchdog_healthy,
        "broker_available": state.broker_available,
        "live_authorization_valid": state.live_authorization_valid,
    }
    values.update(changes)
    return RuntimeDependencyState(**values)


def build_production_runtime(
    config: DeploymentConfig,
    *,
    dependency_state: RuntimeDependencyState | None = None,
    dependencies: RuntimeDependencyBundle | None = None,
    persistence_recovery: PersistenceRecoveryRuntimeWiring | None = None,
    market_feed_runtime: MarketFeedRuntimeWiring | None = None,
    scanner_runtime: ScannerRuntimeWiring | None = None,
    watchdog_runtime: HealthRegistryWatchdogProbe | None = None,
    broker_runtime: BrokerRuntimeWiring | None = None,
    control_runtime: ControlRuntimeWiring | None = None,
    authorization_runtime: LiveAuthorizationRuntimeWiring | None = None,
    postgres_runtime: PostgreSQLRuntimeAdapter | None = None,
) -> RuntimeApplication:
    """Build the canonical runtime with refreshable dependency health.

    The initial dependency snapshot and every subsequent supervisory cycle use
    the same refresher, preventing stale health booleans from persisting after
    a dependency changes state. No broker order is submitted by this function.
    """
    config.validate_filesystem()
    state = dependency_state or RuntimeDependencyState()
    if dependencies is not None:
        dependencies.ensure_structurally_wired()

    refresher = RuntimeDependencyHealthRefresher(
        state=state,
        dependencies=dependencies,
        persistence_recovery=persistence_recovery,
        market_feed_runtime=market_feed_runtime,
        scanner_runtime=scanner_runtime,
        watchdog_runtime=watchdog_runtime,
        broker_runtime=broker_runtime,
        control_runtime=control_runtime,
        authorization_runtime=authorization_runtime,
        postgres_runtime=postgres_runtime,
        config=config,
    )
    state = refresher.refresh()

    signals = ProductionRuntimeSignals(state, config)

    def refresh_signals() -> None:
        signals.state = refresher.refresh()

    def mark_engine_running() -> None:
        refresher.state = _replace_state(refresher.state, engine_running=True)
        signals.state = refresher.state

    def mark_engine_stopped() -> None:
        refresher.state = _replace_state(refresher.state, engine_running=False)
        signals.state = refresher.state

    return RuntimeApplication(
        config=RuntimeConfig(
            service_name=config.service_name,
            poll_interval_seconds=config.runtime_poll_seconds,
        ),
        signals=signals,
        on_start=mark_engine_running,
        on_stop=mark_engine_stopped,
        on_refresh=refresh_signals,
    )
