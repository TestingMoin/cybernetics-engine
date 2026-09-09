from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Dict, Iterable, List, Optional

from .chain_coordinator import ChainSnapshot


@dataclass(frozen=True)
class StrikeSelection:
    strike: float
    ce_security_id: Optional[str]
    pe_security_id: Optional[str]
    distance_from_atm: float


def choose_atm_strike(snapshot: ChainSnapshot) -> Optional[float]:
    if snapshot.underlying_ltp is None or not snapshot.strikes:
        return None
    return min(snapshot.strikes, key=lambda s: abs(s - snapshot.underlying_ltp))


def nearby_strikes(snapshot: ChainSnapshot, count_each_side: int = 5) -> List[StrikeSelection]:
    if count_each_side < 0:
        raise ValueError("count_each_side must be >= 0")
    atm = choose_atm_strike(snapshot)
    if atm is None:
        return []
    ordered = sorted(snapshot.strikes, key=lambda s: abs(s - atm))
    chosen = sorted(ordered[: 2 * count_each_side + 1])
    result: List[StrikeSelection] = []
    for strike in chosen:
        legs = snapshot.strikes.get(strike, {})
        ce = legs.get("ce", {})
        pe = legs.get("pe", {})
        result.append(
            StrikeSelection(
                strike=strike,
                ce_security_id=str(ce["security_id"]) if ce.get("security_id") is not None else None,
                pe_security_id=str(pe["security_id"]) if pe.get("security_id") is not None else None,
                distance_from_atm=abs(strike - atm),
            )
        )
    return result
