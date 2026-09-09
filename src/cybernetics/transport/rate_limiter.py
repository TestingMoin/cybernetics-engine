from __future__ import annotations
from dataclasses import dataclass
from threading import Lock
import time
from collections import deque

@dataclass(frozen=True)
class LimitWindow:
    capacity: int
    seconds: float

class RateLimitGovernor:
    """
    Thread-safe sliding-window governor.

    It blocks before a request would exceed the configured budget.
    Separate governors should be created for independently metered API groups.
    """
    def __init__(self, windows: list[LimitWindow], clock=time.monotonic,
                 sleeper=time.sleep):
        if not windows or any(w.capacity <= 0 or w.seconds <= 0 for w in windows):
            raise ValueError("invalid_rate_limit_windows")
        self._windows=windows
        self._clock=clock
        self._sleep=sleeper
        self._events=deque()
        self._lock=Lock()

    def acquire(self) -> None:
        while True:
            with self._lock:
                now=self._clock()
                # Keep enough timestamps for the largest window.
                max_seconds=max(w.seconds for w in self._windows)
                while self._events and self._events[0] <= now-max_seconds:
                    self._events.popleft()

                wait=0.0
                for w in self._windows:
                    cutoff=now-w.seconds
                    count=sum(1 for ts in self._events if ts > cutoff)
                    if count >= w.capacity:
                        oldest=next(ts for ts in self._events if ts > cutoff)
                        wait=max(wait, (oldest+w.seconds)-now)

                if wait <= 0:
                    self._events.append(now)
                    return
            self._sleep(wait)

class CompositeGovernor:
    def __init__(self, *governors):
        self._governors=governors
    def acquire(self):
        for g in self._governors:
            g.acquire()
