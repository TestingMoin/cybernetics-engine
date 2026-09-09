from __future__ import annotations

import asyncio
import struct
from datetime import datetime, timezone

from cybernetics.market_data.dhan_live_feed import decode_message, decode_packet, FeedPacketError
from cybernetics.market_data.live_client import DhanLiveFeedClient, DhanLiveFeedConfig
from cybernetics.websocket.subscriptions import Instrument, SubscriptionMode


class Secret:
    def get(self, name: str, required: bool = True):
        return "token" if name == "dhan_access_token" else None


class FakeSocket:
    def __init__(self, message: bytes):
        self.message = message
        self.sent = []
        self.closed = False
        self.once = True

    async def send_json(self, payload):
        self.sent.append(payload)

    async def recv(self):
        if self.once:
            self.once = False
            return self.message
        return None

    async def close(self):
        self.closed = True


def ticker_packet() -> bytes:
    return struct.pack("<BHBIfI", 2, 16, 2, 42624, 204.5, 1_757_333_700)


def full_packet() -> bytes:
    depth = b"".join(struct.pack("<IIHHff", 10+i, 20+i, 1, 2, 204.0+i*0.1, 204.5+i*0.1) for i in range(5))
    return struct.pack(
        "<BHBIfHIfIIIIIIffff100s",
        8, 162, 5, 576388, 204.5, 3, 1_757_333_700, 203.9,
        1200, 100, 200, 8500, 9000, 7000, 200.0, 205.0, 210.0, 190.0, depth,
    )


def test_ticker_decode():
    tick = decode_packet(ticker_packet())
    assert tick.kind == "TICKER"
    assert tick.header.exchange_segment == "NSE_FNO"
    assert tick.header.security_id == "42624"
    assert tick.ltp == 204.5
    assert tick.last_trade_time == datetime.fromtimestamp(1_757_333_700, tz=timezone.utc)


def test_full_decode():
    tick = decode_packet(full_packet())
    assert tick.kind == "FULL"
    assert tick.header.exchange_segment == "MCX_COMM"
    assert tick.open_interest == 8500
    assert len(tick.depth) == 5
    assert tick.depth[0]["bid_quantity"] == 10


def test_concatenated_message():
    packets = decode_message(ticker_packet() + ticker_packet())
    assert len(packets) == 2


def test_truncated_packet_fails_closed():
    try:
        decode_packet(ticker_packet()[:-1])
    except FeedPacketError:
        pass
    else:
        raise AssertionError("truncated packet was accepted")


def test_config_does_not_expose_token_in_url_structure():
    cfg = DhanLiveFeedConfig("1108482500", Secret())
    url = cfg.url()
    assert "api-feed.dhan.co" in url
    assert "clientId=1108482500" in url
    assert "authType=2" in url
    assert "token=token" in url


def test_client_subscribes_and_decodes_read_only():
    async def run():
        sock = FakeSocket(ticker_packet())
        received = []
        async def factory(_url):
            return sock
        client = None

        def on_tick(tick):
            received.append(tick)
            client._stop = True

        client = DhanLiveFeedClient(
            DhanLiveFeedConfig("1108482500", Secret()),
            factory,
            shard_id=1,
            on_tick=on_tick,
        )
        client.set_instruments([Instrument("NSE_FNO", "42624")], SubscriptionMode.TICKER)
        await client.connect_once()
        await client.consume_once()
        await client.stop()
        assert received and received[0].kind == "TICKER"
        assert sock.sent[0]["RequestCode"] == 15
        assert sock.closed is True

    asyncio.run(run())
