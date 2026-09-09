from __future__ import annotations
from dataclasses import dataclass
from .sharder import FeedShard, FeedSharder
from .health import FeedHealthMonitor, FeedHealthState
from cybernetics.websocket.subscriptions import Instrument, SubscriptionMode

@dataclass(frozen=True)
class FeedAssignment:
    generation:int
    shards:tuple[FeedShard,...]

class FeedSupervisor:
    """Coordinates universe partitioning and feed health without owning trading logic."""
    def __init__(self, sharder:FeedSharder|None=None,
                 health:FeedHealthMonitor|None=None):
        self.sharder=sharder or FeedSharder()
        self.health=health or FeedHealthMonitor()
        self.generation=0
        self.assignment=FeedAssignment(0,tuple())

    def assign(self,instruments:list[Instrument],
               mode:SubscriptionMode=SubscriptionMode.FULL)->FeedAssignment:
        shards=self.sharder.shard(instruments,mode)
        self.generation+=1
        self.assignment=FeedAssignment(self.generation,tuple(shards))
        for shard in shards:
            self.health.register(shard.shard_id)
        return self.assignment

    def safe_for_market_state(self)->bool:
        states=self.health.evaluate()
        if not states:
            return False
        return all(state==FeedHealthState.HEALTHY for state in states.values())

    def unhealthy_shards(self)->list[int]:
        self.health.evaluate()
        return self.health.unhealthy()
