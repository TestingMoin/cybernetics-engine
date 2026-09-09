from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from typing import Iterable, Optional

from .models import ContractSpec


@dataclass(frozen=True)
class SelectionPolicy:
    underlying_symbol: str
    as_of: date
    min_days_to_expiry: int = 0
    max_days_to_expiry: Optional[int] = None
    require_active: bool = True


class ContractSelector:
    """Selects from a prevalidated instrument master; it never invents contracts."""

    @staticmethod
    def select(contracts: Iterable[ContractSpec], policy: SelectionPolicy) -> ContractSpec:
        candidates = []
        for c in contracts:
            if c.underlying_symbol != policy.underlying_symbol:
                continue
            if policy.require_active and not c.active:
                continue
            days = (c.expiry - policy.as_of).days
            if days < policy.min_days_to_expiry:
                continue
            if policy.max_days_to_expiry is not None and days > policy.max_days_to_expiry:
                continue
            candidates.append((days, c))
        if not candidates:
            raise LookupError(f"no eligible futures contract for {policy.underlying_symbol}")
        candidates.sort(key=lambda item: (item[0], item[1].security_id))
        return candidates[0][1]
