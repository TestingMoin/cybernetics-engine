from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Iterable, Protocol
from urllib.parse import urlencode

from cybernetics.feed_supervisor.health import FeedHealthMonitor
from cybernetics.market_data.dhan_live_feed import MarketTick, decode_message
from cybernetics.websocket.subscriptions import Instrument, SubscriptionManager, SubscriptionMode


class SecretReader(Protocol):
    def get(self, name: str, required: bool = True) -> str | None: ...


@dataclass(frozen=True)
class DhanLiveFeedConfig:
    client_id: str
    secret_provider: SecretReader
    websocket_url: str = "wss://api-feed.dhan.co"
    auth_type: int = 2
    version: int = 2

    def url(self) -> str:
        token = self.secret_provider.get("dhan_access_token")
        if not token:
            raise RuntimeError("market_feed_access_token_missing")
        if not self.client_id:
            raise RuntimeError("market_feed_client_id_missing")
        return self.websocket_url + "?" + urlencode({
            "version": self.version,
            "token": token,
            "clientId": self.client_id,
            "authType": self.auth_type,
        })


class DhanLiveFeedClient:
    """Read-only Dhan V2 websocket boundary.

    This layer receives market data only. It has no broker order-placement or
    cancellation capability. Socket creation is injected for deterministic tests.
    """

    def __init__(
        self,
        config: DhanLiveFeedConfig,
        socket_factory: Callable[[str], Awaitable[Any]],
        *,
        subscriptions: SubscriptionManager | None = None,
        health: FeedHealthMonitor | None = None,
        shard_id: int = 1,
        on_tick: Callable[[MarketTick], Awaitable[None] | None] | None = None,
    ) -> None:
        self.config = config
        self.socket_factory = socket_factory
        self.subscriptions = subscriptions or SubscriptionManager()
        self.health = health or FeedHealthMonitor()
        self.shard_id = shard_id
        self.on_tick = on_tick
        self._socket: Any = None
        self._stop = False

    def set_instruments(self, instruments: Iterable[Instrument], mode: SubscriptionMode = SubscriptionMode.FULL) -> None:
        self.subscriptions.set_desired(mode, instruments)
        self.health.register(self.shard_id)

    async def connect_once(self) -> None:
        self._stop = False
        self._socket = await self.socket_factory(self.config.url())
        self.health.connected(self.shard_id)
        for mode in SubscriptionMode:
            for message in self.subscriptions.messages(mode, subscribe=True):
                await self._socket.send_json(message)

    async def consume_once(self) -> None:
        if self._socket is None:
            raise RuntimeError("market_feed_socket_not_connected")
        while not self._stop:
            message = await self._socket.recv()
            if message is None:
                raise ConnectionError("market_feed_disconnected")
            if not isinstance(message, (bytes, bytearray, memoryview)):
                raise RuntimeError("market_feed_expected_binary_message")
            self.health.received(self.shard_id, binary=True)
            for tick in decode_message(bytes(message)):
                if self.on_tick is not None:
                    result = self.on_tick(tick)
                    if asyncio.iscoroutine(result):
                        await result

    async def stop(self) -> None:
        self._stop = True
        if self._socket is not None:
            close = getattr(self._socket, "close", None)
            if close is not None:
                result = close()
                if asyncio.iscoroutine(result):
                    await result
        self._socket = None
        self.health.disconnected(self.shard_id, error="client_stopped")
