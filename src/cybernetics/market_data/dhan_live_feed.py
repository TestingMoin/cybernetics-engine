from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from struct import calcsize, unpack_from
from typing import Any, Mapping


class FeedPacketError(ValueError):
    """Raised when a Dhan V2 binary market-feed packet is malformed."""


RESPONSE_TICKER = 2
RESPONSE_QUOTE = 4
RESPONSE_PREV_CLOSE = 6
RESPONSE_OI = 5
RESPONSE_FULL = 8
RESPONSE_DISCONNECT = 50
RESPONSE_STATUS = 7

EXCHANGE_SEGMENTS: dict[int, str] = {
    0: "IDX_I",
    1: "NSE_EQ",
    2: "NSE_FNO",
    3: "NSE_CURRENCY",
    4: "BSE_EQ",
    5: "MCX_COMM",
    7: "BSE_CURRENCY",
    8: "BSE_FNO",
}

_HEADER = "<BHBI"
_HEADER_SIZE = calcsize(_HEADER)


@dataclass(frozen=True)
class FeedHeader:
    response_code: int
    message_length: int
    exchange_code: int
    exchange_segment: str
    security_id: str


@dataclass(frozen=True)
class MarketTick:
    header: FeedHeader
    kind: str
    ltp: float | None = None
    last_trade_time: datetime | None = None
    previous_close: float | None = None
    open_interest: int | None = None
    last_trade_quantity: int | None = None
    average_trade_price: float | None = None
    volume: int | None = None
    total_sell_quantity: int | None = None
    total_buy_quantity: int | None = None
    day_open: float | None = None
    day_close: float | None = None
    day_high: float | None = None
    day_low: float | None = None
    oi_high: int | None = None
    oi_low: int | None = None
    depth: tuple[Mapping[str, Any], ...] = ()
    disconnect_code: int | None = None


def parse_header(packet: bytes) -> FeedHeader:
    if len(packet) < _HEADER_SIZE:
        raise FeedPacketError("feed_packet_short_header")
    response_code, message_length, exchange_code, security_id = unpack_from(_HEADER, packet, 0)
    if message_length < _HEADER_SIZE:
        raise FeedPacketError("feed_message_length_invalid")
    if len(packet) < message_length:
        raise FeedPacketError("feed_packet_truncated")
    return FeedHeader(
        response_code=int(response_code),
        message_length=int(message_length),
        exchange_code=int(exchange_code),
        exchange_segment=EXCHANGE_SEGMENTS.get(int(exchange_code), str(exchange_code)),
        security_id=str(int(security_id)),
    )


def decode_packet(packet: bytes) -> MarketTick:
    """Decode one complete Dhan V2 live-feed packet.

    Dhan documents little-endian binary packets with an 8-byte response header.
    Unknown response codes and truncated packets fail closed.
    """
    header = parse_header(packet)
    data = packet[: header.message_length]
    code = header.response_code

    if code == RESPONSE_TICKER:
        _require_size(data, 16, "ticker_packet_short")
        _ltp, _ltt = unpack_from("<fI", data, 8)
        return MarketTick(header, "TICKER", ltp=float(_ltp), last_trade_time=_epoch(_ltt))

    if code == RESPONSE_PREV_CLOSE:
        _require_size(data, 16, "prev_close_packet_short")
        previous_close, prev_oi = unpack_from("<fI", data, 8)
        return MarketTick(header, "PREV_CLOSE", previous_close=float(previous_close), open_interest=int(prev_oi))

    if code == RESPONSE_OI:
        _require_size(data, 12, "oi_packet_short")
        oi = unpack_from("<I", data, 8)[0]
        return MarketTick(header, "OI", open_interest=int(oi))

    if code == RESPONSE_STATUS:
        _require_size(data, 8, "status_packet_short")
        return MarketTick(header, "STATUS")

    if code == RESPONSE_DISCONNECT:
        _require_size(data, 10, "disconnect_packet_short")
        reason = unpack_from("<H", data, 8)[0]
        return MarketTick(header, "DISCONNECT", disconnect_code=int(reason))

    if code == RESPONSE_QUOTE:
        _require_size(data, 50, "quote_packet_short")
        values = unpack_from("<BHBIfHIfIIIffff", data[:50])
        _, _, _, _, ltp, ltq, ltt, atp, volume, sell_qty, buy_qty, day_open, day_close, day_high, day_low = values
        return MarketTick(
            header,
            "QUOTE",
            ltp=float(ltp),
            last_trade_time=_epoch(ltt),
            last_trade_quantity=int(ltq),
            average_trade_price=float(atp),
            volume=int(volume),
            total_sell_quantity=int(sell_qty),
            total_buy_quantity=int(buy_qty),
            day_open=float(day_open),
            day_close=float(day_close),
            day_high=float(day_high),
            day_low=float(day_low),
        )

    if code == RESPONSE_FULL:
        _require_size(data, 162, "full_packet_short")
        values = unpack_from("<BHBIfHIfIIIIIIffff100s", data[:162])
        (_, _, _, _, ltp, ltq, ltt, atp, volume, sell_qty, buy_qty, oi, oi_high, oi_low,
         day_open, day_close, day_high, day_low, depth_bytes) = values
        depth = []
        for offset in range(0, 100, 20):
            bid_qty, ask_qty, bid_orders, ask_orders, bid_price, ask_price = unpack_from(
                "<IIHHff", depth_bytes, offset
            )
            depth.append({
                "bid_quantity": int(bid_qty),
                "ask_quantity": int(ask_qty),
                "bid_orders": int(bid_orders),
                "ask_orders": int(ask_orders),
                "bid_price": float(bid_price),
                "ask_price": float(ask_price),
            })
        return MarketTick(
            header,
            "FULL",
            ltp=float(ltp),
            last_trade_time=_epoch(ltt),
            last_trade_quantity=int(ltq),
            average_trade_price=float(atp),
            volume=int(volume),
            total_sell_quantity=int(sell_qty),
            total_buy_quantity=int(buy_qty),
            open_interest=int(oi),
            oi_high=int(oi_high),
            oi_low=int(oi_low),
            day_open=float(day_open),
            day_close=float(day_close),
            day_high=float(day_high),
            day_low=float(day_low),
            depth=tuple(depth),
        )

    raise FeedPacketError(f"unsupported_feed_response_code:{code}")


def decode_message(message: bytes) -> tuple[MarketTick, ...]:
    """Decode one websocket binary message containing one or more packets."""
    if not message:
        raise FeedPacketError("empty_feed_message")
    packets: list[MarketTick] = []
    offset = 0
    while offset < len(message):
        if len(message) - offset < _HEADER_SIZE:
            raise FeedPacketError("concatenated_message_short_header")
        _code, message_length, _exchange, _security = unpack_from(_HEADER, message, offset)
        if message_length < _HEADER_SIZE:
            raise FeedPacketError("concatenated_message_invalid_length")
        end = offset + int(message_length)
        if end > len(message):
            raise FeedPacketError("concatenated_message_truncated")
        packets.append(decode_packet(message[offset:end]))
        offset = end
    return tuple(packets)


def _require_size(packet: bytes, minimum: int, error: str) -> None:
    if len(packet) < minimum:
        raise FeedPacketError(error)


def _epoch(value: int) -> datetime:
    return datetime.fromtimestamp(int(value), tz=timezone.utc)
