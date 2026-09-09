from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, Any

@dataclass(frozen=True)
class RecoveryWindow:
    start: datetime
    end: datetime

@dataclass(frozen=True)
class MarketDataRecoveryPlan:
    windows: tuple[RecoveryWindow,...]
    interval: str

class MarketDataRecoveryPlanner:
    """
    Creates bounded recovery windows for missing candle ranges.

    Dhan intraday history permits minute intervals 1/5/15/25/60 and a maximum
    90-day polling range per request. The planner never creates a window longer
    than the configured maximum.
    """
    def __init__(self, max_days:int=90):
        if max_days<=0:
            raise ValueError("max_days_must_be_positive")
        self.max_days=max_days

    def plan(self,start:datetime,end:datetime,interval:str="1") -> MarketDataRecoveryPlan:
        if end<=start:
            raise ValueError("recovery_end_must_follow_start")
        if interval not in {"1","5","15","25","60"}:
            raise ValueError("unsupported_intraday_interval")
        windows=[]
        cursor=start
        span=timedelta(days=self.max_days)
        while cursor<end:
            nxt=min(end,cursor+span)
            windows.append(RecoveryWindow(cursor,nxt))
            cursor=nxt
        return MarketDataRecoveryPlan(tuple(windows),interval)

def recover_windows(plan:MarketDataRecoveryPlan,
                    fetch:Callable[[RecoveryWindow,str],Any]):
    """Fetches every planned window in order; caller owns dedupe/persistence."""
    return [fetch(window,plan.interval) for window in plan.windows]
