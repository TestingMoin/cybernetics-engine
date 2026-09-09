from __future__ import annotations
import json
from typing import Any
import websockets

class DhanWebSocketTransport:
    def __init__(self, socket: Any) -> None:
        self._socket = socket
    async def send_json(self, payload: Any) -> None:
        await self._socket.send(json.dumps(payload,separators=(",",":"),ensure_ascii=False))
    async def recv(self) -> Any:
        return await self._socket.recv()
    async def close(self) -> None:
        await self._socket.close()

async def dhan_websocket_factory(url: str) -> DhanWebSocketTransport:
    return DhanWebSocketTransport(await websockets.connect(url))
