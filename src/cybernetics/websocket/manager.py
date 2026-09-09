from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
import asyncio
from typing import Any, Awaitable, Callable, Optional

from .subscriptions import SubscriptionManager, SubscriptionMode

class FeedState(str, Enum):
    DISCONNECTED="DISCONNECTED"
    CONNECTING="CONNECTING"
    AUTHENTICATED="AUTHENTICATED"
    SUBSCRIBING="SUBSCRIBING"
    RUNNING="RUNNING"
    RECONNECT_WAIT="RECONNECT_WAIT"
    STOPPING="STOPPING"
    FAILED="FAILED"

@dataclass(frozen=True)
class ReconnectPolicy:
    base_delay: float=1.0
    max_delay: float=30.0
    max_attempts: int=0  # 0 = unlimited

class DhanMarketFeedManager:
    """
    WebSocket lifecycle controller.

    The actual websocket implementation is injected, keeping the manager
    independent of a particular asyncio WebSocket library.
    """
    WS_URL="wss://api-feed.dhan.co?version=2&token={token}&clientId={client_id}&authType=2"

    def __init__(
        self,
        token_provider: Callable[[],dict[str,str]],
        client_id: str,
        socket_factory: Callable[[str],Awaitable[Any]],
        subscriptions: Optional[SubscriptionManager]=None,
        on_message: Optional[Callable[[Any],Awaitable[None] | None]]=None,
        reconnect: ReconnectPolicy=ReconnectPolicy(),
        sleep: Callable[[float],Awaitable[None]]=asyncio.sleep,
    ):
        if not client_id:
            raise ValueError("client_id_required")
        if reconnect.base_delay<=0 or reconnect.max_delay<reconnect.base_delay:
            raise ValueError("invalid_reconnect_policy")
        self._token_provider=token_provider
        self._client_id=client_id
        self._socket_factory=socket_factory
        self.subscriptions=subscriptions or SubscriptionManager()
        self._on_message=on_message
        self._reconnect=reconnect
        self._sleep=sleep
        self.state=FeedState.DISCONNECTED
        self._socket=None
        self._stop=False
        self._attempt=0

    def url(self)->str:
        token=self._token_provider().get("access-token")
        if not token:
            raise RuntimeError("market_feed_access_token_missing")
        return self.WS_URL.format(token=token,client_id=self._client_id)

    async def connect_once(self):
        self.state=FeedState.CONNECTING
        self._socket=await self._socket_factory(self.url())
        self.state=FeedState.AUTHENTICATED
        await self._resubscribe()
        self.state=FeedState.RUNNING
        self._attempt=0

    async def _resubscribe(self):
        self.state=FeedState.SUBSCRIBING
        for mode in SubscriptionMode:
            for message in self.subscriptions.messages(mode,subscribe=True):
                await self._socket.send_json(message)

    async def run(self):
        self._stop=False
        while not self._stop:
            try:
                await self.connect_once()
                await self._consume()
            except asyncio.CancelledError:
                raise
            except Exception:
                if self._stop:
                    break
                self.state=FeedState.RECONNECT_WAIT
                self._attempt+=1
                if self._reconnect.max_attempts and self._attempt>self._reconnect.max_attempts:
                    self.state=FeedState.FAILED
                    break
                delay=min(
                    self._reconnect.max_delay,
                    self._reconnect.base_delay*(2**max(0,self._attempt-1)),
                )
                await self._sleep(delay)

    async def _consume(self):
        while not self._stop:
            message=await self._socket.recv()
            if message is None:
                raise ConnectionError("market_feed_disconnected")
            if self._on_message is not None:
                result=self._on_message(message)
                if asyncio.iscoroutine(result):
                    await result

    async def stop(self):
        self._stop=True
        self.state=FeedState.STOPPING
        if self._socket is not None:
            close=getattr(self._socket,"close",None)
            if close is not None:
                result=close()
                if asyncio.iscoroutine(result):
                    await result
        self._socket=None
        self.state=FeedState.DISCONNECTED
