from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Any
from .gap_detector import DataGap

class RecoveryState(str, Enum):
    IDLE="IDLE"
    REQUESTED="REQUESTED"
    FETCHING="FETCHING"
    MERGING="MERGING"
    VERIFIED="VERIFIED"
    FAILED="FAILED"
    BLOCKED="BLOCKED"

@dataclass(frozen=True)
class RecoveryResult:
    gap: DataGap
    state: RecoveryState
    recovered_count: int
    duplicate_count: int
    message: str

class RecoveryCoordinator:
    """
    Coordinates fetch -> dedupe -> merge -> verify.

    The merge callback must be atomic from the perspective of the canonical
    state store. The coordinator never overwrites an existing candle blindly.
    """
    def __init__(
        self,
        fetch: Callable[[DataGap], list[dict[str,Any]]],
        merge: Callable[[list[dict[str,Any]]], tuple[int,int]],
        verify: Callable[[DataGap], bool],
    ):
        self._fetch=fetch
        self._merge=merge
        self._verify=verify

    def recover(self, gap: DataGap) -> RecoveryResult:
        state=RecoveryState.REQUESTED
        try:
            state=RecoveryState.FETCHING
            rows=self._fetch(gap)
            if rows is None:
                return RecoveryResult(gap,RecoveryState.FAILED,0,0,"fetch_returned_none")

            state=RecoveryState.MERGING
            recovered,duplicates=self._merge(self._dedupe_rows(rows))

            state=RecoveryState.VERIFIED
            if not self._verify(gap):
                return RecoveryResult(gap,RecoveryState.FAILED,recovered,duplicates,
                                      "gap_remains_after_recovery")

            return RecoveryResult(gap,state,recovered,duplicates,"recovery_verified")
        except PermissionError as exc:
            return RecoveryResult(gap,RecoveryState.BLOCKED,0,0,f"permission:{exc}")
        except Exception as exc:
            return RecoveryResult(gap,RecoveryState.FAILED,0,0,
                                  f"{type(exc).__name__}:{exc}")

    @staticmethod
    def _dedupe_rows(rows:list[dict[str,Any]])->list[dict[str,Any]]:
        seen=set()
        out=[]
        for row in rows:
            ts=row.get("timestamp")
            if ts is None:
                raise ValueError("recovery_row_missing_timestamp")
            if ts not in seen:
                seen.add(ts)
                out.append(row)
        out.sort(key=lambda x:x["timestamp"])
        return out
