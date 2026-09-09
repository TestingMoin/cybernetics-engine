from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping


class DependencyWiringError(ValueError):
    """Raised when the canonical runtime dependency graph is incomplete."""


@dataclass(frozen=True)
class DependencyBinding:
    """One explicit runtime dependency plus its side-effect-free readiness probe."""

    name: str
    component: object
    ready: Callable[[object], bool]

    def is_ready(self) -> bool:
        return bool(self.ready(self.component))


REQUIRED_RUNTIME_DEPENDENCIES: tuple[str, ...] = (
    "persistence",
    "recovery",
    "market_data",
    "scanners",
    "watchdog",
    "control",
    "broker",
)


@dataclass(frozen=True)
class RuntimeDependencyBundle:
    """Canonical dependency bundle owned by the production composition root.

    Every runtime-critical subsystem is injected explicitly.  The bundle itself
    never performs I/O; readiness is obtained only through injected probes.
    """

    persistence: DependencyBinding
    recovery: DependencyBinding
    market_data: DependencyBinding
    scanners: DependencyBinding
    watchdog: DependencyBinding
    control: DependencyBinding
    broker: DependencyBinding

    @classmethod
    def from_components(
        cls,
        *,
        persistence: object,
        recovery: object,
        market_data: object,
        scanners: object,
        watchdog: object,
        control: object,
        broker: object,
        readiness: Mapping[str, Callable[[object], bool]],
    ) -> "RuntimeDependencyBundle":
        components = {
            "persistence": persistence,
            "recovery": recovery,
            "market_data": market_data,
            "scanners": scanners,
            "watchdog": watchdog,
            "control": control,
            "broker": broker,
        }
        missing_probes = [name for name in REQUIRED_RUNTIME_DEPENDENCIES if name not in readiness]
        if missing_probes:
            raise DependencyWiringError(
                "missing_readiness_probes:" + ",".join(missing_probes)
            )
        missing_components = [name for name, value in components.items() if value is None]
        if missing_components:
            raise DependencyWiringError(
                "missing_runtime_dependencies:" + ",".join(missing_components)
            )
        return cls(
            **{
                name: DependencyBinding(name, components[name], readiness[name])
                for name in REQUIRED_RUNTIME_DEPENDENCIES
            }
        )

    def bindings(self) -> tuple[DependencyBinding, ...]:
        return tuple(getattr(self, name) for name in REQUIRED_RUNTIME_DEPENDENCIES)

    def readiness(self) -> dict[str, bool]:
        return {binding.name: binding.is_ready() for binding in self.bindings()}

    def audit(self) -> tuple[str, ...]:
        """Return deterministic structural/runtime readiness findings."""
        findings: list[str] = []
        for binding in self.bindings():
            if binding.component is None:
                findings.append(f"{binding.name}:component_missing")
            try:
                binding.ready(binding.component)
            except Exception as exc:
                findings.append(f"{binding.name}:readiness_probe_error:{type(exc).__name__}")
        return tuple(findings)

    def ensure_structurally_wired(self) -> None:
        findings = self.audit()
        structural = tuple(item for item in findings if item.endswith(":component_missing") or item.startswith("missing_"))
        if structural:
            raise DependencyWiringError(";".join(structural))

    def as_dependency_state(self, *, base_state) -> object:
        """Project dependency probes into the existing runtime state model."""
        readiness = self.readiness()
        return type(base_state)(
            engine_running=base_state.engine_running,
            control_state=base_state.control_state,
            emergency_state=base_state.emergency_state,
            persistence_ready=readiness["persistence"],
            recovery_clear=readiness["recovery"],
            orders_reconciled=base_state.orders_reconciled,
            positions_reconciled=base_state.positions_reconciled,
            market_data_ready=readiness["market_data"],
            scanner_health_ready=readiness["scanners"],
            watchdog_healthy=readiness["watchdog"],
            broker_available=readiness["broker"],
            live_authorization_valid=base_state.live_authorization_valid,
        )
