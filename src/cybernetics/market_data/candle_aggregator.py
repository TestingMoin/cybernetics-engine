from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable

from .dhan_live_feed import MarketTick
from cybernetics.state.store import Candle, CanonicalMarketStateStore


SUPPORTED_TIMEFRAMES: dict[str, int] = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "1h": 3600,
}


@dataclass(frozen=True)
class CandleKey:
    security_id: str
    timeframe: str
    start: datetime


@dataclass
class _WorkingCandle:
    security_id: str
    timeframe: str
    start: datetime
    end: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    source: str = "LIVE"

    def update(self, price: float, volume_delta: float) -> None:
        self.high = max(self.high, price)
        self.low = min(self.low, price)
        self.close = price
        self.volume += volume_delta

    def finalize(self) -> Candle:
        return Candle(
            security_id=self.security_id,
            timestamp=self.start,
            open=self.open,
            high=self.high,
            low=self.low,
            close=self.close,
            volume=self.volume,
            source=self.source,
        )


@dataclass(frozen=True)
class AggregationResult:
    security_id: str
    timeframe: str
    candle: Candle | None
    accepted: bool
    reason: str


class LiveCandleAggregator:
    """
    Deterministic live tick -> OHLCV candle aggregator.

    Rules:
    - Uses the Dhan trade timestamp, never wall-clock time.
    - Stores candle timestamps as UTC.
    - Candle timestamp means candle START.
    - Only finalized candles are emitted.
    - Dhan volume is cumulative; candle volume uses positive deltas.
    - Duplicate ticks do not alter candle state.
    - Older ticks cannot mutate an already-progressed candle.
    - A cumulative-volume reset is treated as zero volume contribution.
    - No REST recovery is performed here.
    - No broker/execution operations are performed here.
    """

    def __init__(
        self,
        store: CanonicalMarketStateStore,
        on_candle: Callable[[Candle], None] | None = None,
    ) -> None:
        self._store = store
        self._on_candle = on_candle

        self._working: dict[tuple[str, str], _WorkingCandle] = {}
        self._last_tick_time: dict[str, datetime] = {}
        self._last_tick_signature: dict[str, tuple[datetime, float, int | None]] = {}
        self._last_cumulative_volume: dict[str, int] = {}

    @staticmethod
    def validate_timeframe(timeframe: str) -> None:
        if timeframe not in SUPPORTED_TIMEFRAMES:
            raise ValueError(f"unsupported_timeframe:{timeframe}")

    @staticmethod
    def bucket_start(timestamp: datetime, timeframe: str) -> datetime:
        LiveCandleAggregator.validate_timeframe(timeframe)

        if timestamp.tzinfo is None:
            raise ValueError("tick_timestamp_must_be_timezone_aware")

        ts = timestamp.astimezone(timezone.utc)
        seconds = int(ts.timestamp())
        interval = SUPPORTED_TIMEFRAMES[timeframe]
        bucket_seconds = seconds - (seconds % interval)

        return datetime.fromtimestamp(bucket_seconds, tz=timezone.utc)

    @staticmethod
    def bucket_end(start: datetime, timeframe: str) -> datetime:
        LiveCandleAggregator.validate_timeframe(timeframe)
        return start + timedelta(seconds=SUPPORTED_TIMEFRAMES[timeframe])

    def ingest(self, tick: MarketTick, timeframe: str) -> AggregationResult:
        self.validate_timeframe(timeframe)

        if tick.ltp is None:
            return AggregationResult(
                tick.header.security_id,
                timeframe,
                None,
                False,
                "tick_ltp_missing",
            )

        if tick.last_trade_time is None:
            return AggregationResult(
                tick.header.security_id,
                timeframe,
                None,
                False,
                "tick_timestamp_missing",
            )

        security_id = tick.header.security_id
        timestamp = tick.last_trade_time.astimezone(timezone.utc)
        price = float(tick.ltp)

        if price <= 0:
            return AggregationResult(
                security_id,
                timeframe,
                None,
                False,
                "tick_ltp_invalid",
            )

        previous_time = self._last_tick_time.get(security_id)

        if previous_time is not None and timestamp < previous_time:
            return AggregationResult(
                security_id,
                timeframe,
                None,
                False,
                "tick_out_of_order",
            )

        signature = (
            timestamp,
            price,
            tick.volume,
        )

        if self._last_tick_signature.get(security_id) == signature:
            return AggregationResult(
                security_id,
                timeframe,
                None,
                False,
                "duplicate_tick",
            )

        volume_delta = self._volume_delta(security_id, tick.volume)

        self._last_tick_time[security_id] = timestamp
        self._last_tick_signature[security_id] = signature

        bucket = self.bucket_start(timestamp, timeframe)
        key = (security_id, timeframe)
        working = self._working.get(key)

        if working is None:
            self._working[key] = _WorkingCandle(
                security_id=security_id,
                timeframe=timeframe,
                start=bucket,
                end=self.bucket_end(bucket, timeframe),
                open=price,
                high=price,
                low=price,
                close=price,
                volume=volume_delta,
            )
            return AggregationResult(
                security_id,
                timeframe,
                None,
                True,
                "candle_started",
            )

        if bucket < working.start:
            return AggregationResult(
                security_id,
                timeframe,
                None,
                False,
                "tick_belongs_to_closed_bucket",
            )

        if bucket == working.start:
            working.update(price, volume_delta)
            return AggregationResult(
                security_id,
                timeframe,
                None,
                True,
                "candle_updated",
            )

        finalized = working.finalize()

        self._store.upsert(finalized)

        if self._on_candle is not None:
            self._on_candle(finalized)

        self._working[key] = _WorkingCandle(
            security_id=security_id,
            timeframe=timeframe,
            start=bucket,
            end=self.bucket_end(bucket, timeframe),
            open=price,
            high=price,
            low=price,
            close=price,
            volume=volume_delta,
        )

        return AggregationResult(
            security_id,
            timeframe,
            finalized,
            True,
            "candle_finalized",
        )

    def finalize(self, security_id: str, timeframe: str) -> Candle | None:
        """
        Explicitly finalize the current working candle.

        This is intended for controlled shutdown/session handling.
        It does not manufacture a candle when no tick exists.
        """
        self.validate_timeframe(timeframe)

        key = (security_id, timeframe)
        working = self._working.pop(key, None)

        if working is None:
            return None

        candle = working.finalize()
        self._store.upsert(candle)

        if self._on_candle is not None:
            self._on_candle(candle)

        return candle

    def working(self, security_id: str, timeframe: str) -> Candle | None:
        working = self._working.get((security_id, timeframe))

        if working is None:
            return None

        return Candle(
            security_id=working.security_id,
            timestamp=working.start,
            open=working.open,
            high=working.high,
            low=working.low,
            close=working.close,
            volume=working.volume,
            source=working.source,
        )

    def _volume_delta(self, security_id: str, cumulative_volume: int | None) -> float:
        if cumulative_volume is None:
            return 0.0

        if cumulative_volume < 0:
            raise ValueError("tick_volume_negative")

        previous = self._last_cumulative_volume.get(security_id)
        self._last_cumulative_volume[security_id] = cumulative_volume

        if previous is None:
            return 0.0

        if cumulative_volume < previous:
            # Dhan cumulative volume may reset after a session/reconnect.
            # Never create negative candle volume.
            return 0.0

        return float(cumulative_volume - previous)
