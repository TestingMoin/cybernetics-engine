from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable

@dataclass(frozen=True)
class ScannerGroup:
    group_id: str
    scanner_name: str
    asset_types: tuple[str, ...]
    timeframes: tuple[str, ...]
    enabled: bool = False
    market_hours: tuple[str, ...] = ()
    options_required: bool = False
    risk_profile: str = "STANDARD"

class ScannerGroupRegistry:
    """Registry for logical scanner instances; one engine implementation can serve many groups."""
    def __init__(self, groups: Iterable[ScannerGroup] = ()):
        self._groups: dict[str, ScannerGroup] = {}
        for group in groups:
            self.register(group)

    def register(self, group: ScannerGroup) -> None:
        if group.group_id in self._groups:
            raise ValueError(f"duplicate_scanner_group:{group.group_id}")
        self._groups[group.group_id] = group

    def get(self, group_id: str) -> ScannerGroup:
        try:
            return self._groups[group_id]
        except KeyError:
            raise KeyError(f"scanner_group_not_found:{group_id}")

    def enabled(self) -> list[ScannerGroup]:
        return [g for g in self._groups.values() if g.enabled]

    def all(self) -> list[ScannerGroup]:
        return list(self._groups.values())
