from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta

@dataclass(frozen=True)
class DataGap:
    security_id: str
    start: datetime
    end: datetime
    interval: timedelta
    missing_bars: int

class GapDetector:
    """
    Detects missing expected candle timestamps.

    It operates on canonical timestamps already normalized by the market-data
    layer. Session/calendar filtering is intentionally delegated to the caller,
    so the detector does not invent exchange holidays or market hours.
    """
    def detect(self, security_id: str, timestamps: list[datetime],
               expected_interval: timedelta) -> list[DataGap]:
        if expected_interval.total_seconds() <= 0:
            raise ValueError("expected_interval_must_be_positive")
        if len(timestamps) < 2:
            return []

        ordered=sorted(set(timestamps))
        gaps=[]
        for left,right in zip(ordered, ordered[1:]):
            delta=right-left
            if delta > expected_interval:
                missing=max(0,int(delta/expected_interval)-1)
                if missing:
                    gaps.append(
                        DataGap(
                            security_id=security_id,
                            start=left+expected_interval,
                            end=right-expected_interval,
                            interval=expected_interval,
                            missing_bars=missing,
                        )
                    )
        return gaps
