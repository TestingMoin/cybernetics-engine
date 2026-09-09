from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Awaitable, Callable

from cybernetics.market_data.live_client import DhanLiveFeedClient
from cybernetics.market_data.dhan_live_feed import MarketTick


@dataclass(frozen=True)
class FeedRuntimePolicy:
    reconnect_delay_seconds: float = 1.0
    max_reconnect_delay_seconds: float = 30.0
    max_reconnect_attempts: int = 0  # 0 = unlimited
    receive_timeout_seconds: float = 40.0

    def __post_init__(self) -> None:
        if self.reconnect_delay_seconds <= 0:
            raise ValueError("invalid_reconnect_delay")
        if self.max_reconnect_delay_seconds < self.reconnect_delay_seconds:
            raise ValueError("invalid_max_reconnect_delay")
        if self.max_reconnect_attempts < 0:
            raise ValueError("invalid_max_reconnect_attempts")
        if self.receive_timeout_seconds <= 0:
            raise ValueError("invalid_receive_timeout")


class LiveFeedRuntime:
    """Supervises an already-constructed read-only Dhan live-feed client."""

    def __init__(
        self,
        client: DhanLiveFeedClient,
        *,
        on_tick: Callable[[MarketTick], Awaitable[None] | None] | None = None,
        policy: FeedRuntimePolicy = FeedRuntimePolicy(),
    ) -> None:
        self.client = client
        self.on_tick = on_tick
        self.policy = policy
        self.running = False
        self.connected = False
        self.reconnect_attempts = 0
        self.last_error: str | None = None

    async def run_once(self) -> None:
        await self.client.connect_once()
        self.connected = True
        self.reconnect_attempts = 0

        while self.running:
            if self.client._socket is None:
                raise ConnectionError("market_feed_socket_missing")

            message = await asyncio.wait_for(
                self.client._socket.recv(),
                timeout=self.policy.receive_timeout_seconds,
            )

            if message is None:
                raise ConnectionError("market_feed_disconnected")

            if not isinstance(message, (bytes, bytearray, memoryview)):
                raise RuntimeError("market_feed_expected_binary_message")

            from cybernetics.market_data.dhan_live_feed import decode_message

            for tick in decode_message(bytes(message)):
                if self.on_tick is not None:
                    result = self.on_tick(tick)
                    if asyncio.iscoroutine(result):
                        await result

    async def run(self) -> None:
        self.running = True
        self.last_error = None

        while self.running:
            try:
                await self.run_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.connected = False
                self.last_error = type(exc).__name__

                if not self.running:
                    break

                self.reconnect_attempts += 1

                if (
                    self.policy.max_reconnect_attempts
                    and self.reconnect_attempts > self.policy.max_reconnect_attempts
                ):
                    break

                delay = min(
                    self.policy.max_reconnect_delay_seconds,
                    self.policy.reconnect_delay_seconds
                    * (2 ** max(0, self.reconnect_attempts - 1)),
                )
                await asyncio.sleep(delay)

    async def stop(self) -> None:
        self.running = False
        self.connected = False
        await self.client.stop()
