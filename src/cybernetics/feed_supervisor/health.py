from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta, timezone
from typing import Optional

class FeedHealthState(str, Enum):
    HEALTHY="HEALTHY"
    DEGRADED="DEGRADED"
    STALE="STALE"
    DISCONNECTED="DISCONNECTED"
    UNKNOWN="UNKNOWN"

@dataclass
class FeedHealth:
    shard_id:int
    state:FeedHealthState=FeedHealthState.UNKNOWN
    connected_at:Optional[datetime]=None
    last_message_at:Optional[datetime]=None
    last_binary_packet_at:Optional[datetime]=None
    message_count:int=0
    binary_packet_count:int=0
    reconnect_count:int=0
    last_error:Optional[str]=None

class FeedHealthMonitor:
    """
    Supervises feed liveness independently from strategy decisions.

    `stale_after` defines when an otherwise connected shard is considered STALE.
    The monitor does not fabricate a healthy state merely because the socket is open.
    """
    def __init__(self, stale_after:timedelta=timedelta(seconds=15)):
        if stale_after.total_seconds()<=0:
            raise ValueError("stale_after_must_be_positive")
        self.stale_after=stale_after
        self._feeds:dict[int,FeedHealth]={}

    def register(self, shard_id:int)->FeedHealth:
        if shard_id in self._feeds:
            return self._feeds[shard_id]
        h=FeedHealth(shard_id)
        self._feeds[shard_id]=h
        return h

    def connected(self, shard_id:int, when:Optional[datetime]=None)->None:
        h=self.register(shard_id)
        when=when or datetime.now(timezone.utc)
        h.connected_at=when
        h.state=FeedHealthState.DEGRADED

    def received(self, shard_id:int, when:Optional[datetime]=None, binary:bool=True)->None:
        h=self.register(shard_id)
        when=when or datetime.now(timezone.utc)
        h.last_message_at=when
        h.message_count+=1
        if binary:
            h.last_binary_packet_at=when
            h.binary_packet_count+=1
        if h.connected_at is not None:
            h.state=FeedHealthState.HEALTHY

    def disconnected(self, shard_id:int, error:Optional[str]=None)->None:
        h=self.register(shard_id)
        h.state=FeedHealthState.DISCONNECTED
        h.last_error=error

    def reconnected(self, shard_id:int, when:Optional[datetime]=None)->None:
        h=self.register(shard_id)
        h.reconnect_count+=1
        self.connected(shard_id,when)

    def evaluate(self, now:Optional[datetime]=None)->dict[int,FeedHealthState]:
        now=now or datetime.now(timezone.utc)
        for h in self._feeds.values():
            if h.state==FeedHealthState.DISCONNECTED:
                continue
            last=h.last_binary_packet_at or h.last_message_at
            if last is None:
                h.state=FeedHealthState.DEGRADED
                continue
            if now-last>self.stale_after:
                h.state=FeedHealthState.STALE
            else:
                h.state=FeedHealthState.HEALTHY
        return {sid:h.state for sid,h in self._feeds.items()}

    def unhealthy(self)->list[int]:
        return [sid for sid,h in self._feeds.items()
                if h.state in {FeedHealthState.STALE,FeedHealthState.DISCONNECTED}]
