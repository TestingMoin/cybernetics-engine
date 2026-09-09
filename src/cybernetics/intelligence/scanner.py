from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from .iceberg import IcebergDetector, IcebergEvent, MarketObservation

@dataclass(frozen=True)
class ScannerConfig:
    scanner_id: str
    scanner_name: str
    group_id: str
    assets: tuple[str, ...]
    timeframes: tuple[str, ...] = ("1m",)
    enabled: bool = True
    liquidity_threshold: float = 0.0
    volume_threshold: float = 0.0
    iceberg_threshold: float = 0.70
    gap_threshold: float = 0.0
    options_requirement: str = "OPTIONAL"
    risk_profile: str = "DEFAULT"

class IndependentIcebergScanner:
    def __init__(self, config: ScannerConfig, detector: Optional[IcebergDetector] = None):
        self.config = config
        self.detector = detector or IcebergDetector(confidence_threshold=config.iceberg_threshold)
        self.events: list[IcebergEvent] = []

    def process(self, obs: MarketObservation, **kwargs) -> Optional[IcebergEvent]:
        if not self.config.enabled or obs.instrument not in self.config.assets:
            return None
        event = self.detector.detect(obs, **kwargs)
        if event:
            self.events.append(event)
        return event

    def recent(self, limit: int = 50) -> list[IcebergEvent]:
        return self.events[-limit:]

def build_example_scanners() -> dict[str, IndependentIcebergScanner]:
    specs = {
        "ICE-NIFTY": ("NSE-INDEX", ("NIFTY",)),
        "ICE-BANKNIFTY": ("NSE-INDEX", ("BANKNIFTY",)),
        "ICE-FINNIFTY": ("NSE-INDEX", ("FINNIFTY",)),
        "ICE-MIDCPNIFTY": ("NSE-INDEX", ("MIDCPNIFTY",)),
        "ICE-NIFTYNXT50": ("NSE-INDEX", ("NIFTYNXT50",)),
        "ICE-NIFTYFPI": ("NSE-INDEX", ("NIFTYFPI",)),
        "ICE-SENSEX": ("BSE-INDEX", ("SENSEX",)),
        "ICE-BANKEX": ("BSE-INDEX", ("BANKEX",)),
        "ICE-SENSEX50": ("BSE-INDEX", ("SENSEX50",)),
        "ICE-COM-BULLION": ("MCX-BULLION", ("GOLD","GOLDMINI","SILVER","SILVERMINI")),
        "ICE-COM-ENERGY": ("MCX-ENERGY", ("CRUDEOIL","CRUDEOILMINI","NATURALGAS","NATURALGASMINI")),
        "ICE-COM-BASEMETALS": ("MCX-BASEMETALS", ("ALUMINIUM","ALUMINIUMMINI","ZINC","ZINCMINI","COPPER","NICKEL","LEAD","STEELREBAR")),
        "ICE-UNIVERSAL": ("UNIVERSAL", ()),
    }
    out={}
    for sid,(gid,assets) in specs.items():
        out[sid]=IndependentIcebergScanner(
            ScannerConfig(sid,sid,gid,assets)
        )
    return out
