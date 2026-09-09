from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable
from cybernetics.websocket.subscriptions import Instrument, SubscriptionMode

@dataclass(frozen=True)
class FeedShard:
    shard_id: int
    instruments: tuple[Instrument, ...]
    mode: SubscriptionMode = SubscriptionMode.FULL

class FeedSharder:
    """
    Deterministically partitions a universe across <=5 Dhan market-feed connections,
    with <=5000 instruments on each connection.

    The sharder is intentionally pure: assignment changes only when the desired
    universe changes, making audits and recovery reproducible.
    """
    MAX_CONNECTIONS=5
    MAX_INSTRUMENTS_PER_CONNECTION=5000

    def __init__(self, max_connections:int=5, per_connection_limit:int=5000):
        if not 1 <= max_connections <= self.MAX_CONNECTIONS:
            raise ValueError("invalid_max_connections")
        if not 1 <= per_connection_limit <= self.MAX_INSTRUMENTS_PER_CONNECTION:
            raise ValueError("invalid_per_connection_limit")
        self.max_connections=max_connections
        self.per_connection_limit=per_connection_limit

    def shard(self, instruments:Iterable[Instrument],
              mode:SubscriptionMode=SubscriptionMode.FULL)->list[FeedShard]:
        unique=sorted(set(instruments))
        capacity=self.max_connections*self.per_connection_limit
        if len(unique)>capacity:
            raise ValueError("universe_exceeds_feed_capacity")

        count=max(1,(len(unique)+self.per_connection_limit-1)//self.per_connection_limit)
        count=min(count,self.max_connections)

        shards=[[] for _ in range(count)]
        for idx,item in enumerate(unique):
            shards[idx % count].append(item)

        return [
            FeedShard(i+1,tuple(bucket),mode)
            for i,bucket in enumerate(shards) if bucket
        ]

    @staticmethod
    def diff(old:list[FeedShard], new:list[FeedShard]):
        old_set={i for s in old for i in s.instruments}
        new_set={i for s in new for i in s.instruments}
        return {
            "added":tuple(sorted(new_set-old_set)),
            "removed":tuple(sorted(old_set-new_set)),
            "unchanged":tuple(sorted(old_set & new_set)),
        }
