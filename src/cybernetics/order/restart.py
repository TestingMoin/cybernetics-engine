from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable

from .manager import OrderManager, OrderRecord, OrderManagerStatus


@dataclass(frozen=True)
class RecoverySummary:
    loaded_orders: int
    active_orders: int
    unknown_orders: int
    terminal_orders: int


class OrderRecoveryCoordinator:
    """
    Startup recovery over persistent order records.

    It does not fabricate broker state. ACTIVE/UNKNOWN records remain candidates
    for broker reconciliation; terminal records are restored as-is.
    """

    def recover(self, records: Iterable[OrderRecord]) -> RecoverySummary:
        items = list(records)
        active = sum(
            1 for r in items
            if r.status in {OrderManagerStatus.ACTIVE, OrderManagerStatus.PARTIAL}
        )
        unknown = sum(1 for r in items if r.status == OrderManagerStatus.UNKNOWN)
        terminal = sum(
            1 for r in items if r.status in {
                OrderManagerStatus.FILLED,
                OrderManagerStatus.REJECTED,
                OrderManagerStatus.CANCELLED,
                OrderManagerStatus.EXPIRED,
            }
        )
        return RecoverySummary(len(items), active, unknown, terminal)
