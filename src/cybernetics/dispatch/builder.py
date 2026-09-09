from __future__ import annotations
from dataclasses import dataclass
from cybernetics.scanners.models import ScannerRuntimeKey
from .router import RoutingKey, ScannerEventRouter

@dataclass(frozen=True)
class BindingSpec:
    exchange_segment: str
    security_id: str
    timeframe: str
    scanner_id: str
    underlying_key: str

def bind_runtime(router:ScannerEventRouter, spec:BindingSpec)->ScannerRuntimeKey:
    runtime_key=ScannerRuntimeKey(
        spec.scanner_id,
        spec.underlying_key,
        spec.timeframe,
    )
    router.bind(
        RoutingKey(spec.exchange_segment,spec.security_id,spec.timeframe),
        runtime_key,
    )
    return runtime_key
