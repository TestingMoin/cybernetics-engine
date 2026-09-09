from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol

from cybernetics.scanners.models import ScannerRuntime, ScannerRuntimeKey, ScannerState
from cybernetics.scanners.registry import ScannerRuntimeRegistry


class ScannerHealthProbe(Protocol):
    def list(self) -> list[ScannerRuntime]: ...


@dataclass(frozen=True)
class ScannerRuntimeWiring:
    """Read-only runtime boundary for scanner health.

    A scanner subsystem is considered ready only when at least one scanner
    runtime exists and every configured runtime is RUNNING. DEGRADED/STOPPED/
    FAILED/CREATED runtimes fail closed. A custom readiness callable may be
    injected for a production supervisor with richer policy.
    """

    registry: ScannerHealthProbe
    readiness: Callable[[ScannerHealthProbe], bool] | None = None

    def scanner_health_ready(self) -> bool:
        check = self.readiness or self._default_readiness
        try:
            return bool(check(self.registry))
        except Exception:
            return False

    def unhealthy(self) -> bool:
        return not self.scanner_health_ready()

    @staticmethod
    def _default_readiness(component: ScannerHealthProbe) -> bool:
        runtimes = list(component.list())
        return bool(runtimes) and all(runtime.state is ScannerState.RUNNING for runtime in runtimes)


def build_scanner_runtime_wiring(
    *,
    registry: ScannerRuntimeRegistry,
    readiness: Callable[[ScannerHealthProbe], bool] | None = None,
) -> ScannerRuntimeWiring:
    if registry is None:
        raise ValueError("scanner_registry_required")
    return ScannerRuntimeWiring(registry=registry, readiness=readiness)
