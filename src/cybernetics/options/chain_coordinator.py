from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Awaitable, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


@dataclass(frozen=True)
class UnderlyingRef:
    scanner_id: str
    symbol: str
    security_id: int
    exchange_segment: str


@dataclass(frozen=True)
class ChainRequest:
    underlying: UnderlyingRef
    expiry: date
    requested_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ChainSnapshot:
    scanner_id: str
    symbol: str
    security_id: int
    exchange_segment: str
    expiry: date
    underlying_ltp: Optional[float]
    strikes: Dict[float, Dict[str, Dict[str, Any]]]
    fetched_at: datetime
    source: str = "dhan.optionchain"


class UniqueRequestGate:
    """Global gate matching Dhan's unique option-chain request cadence.

    Requests for different underlyings/expiries may proceed together, but the
    coordinator must never issue the same logical request key more frequently
    than the configured interval.
    """

    def __init__(self, min_interval_seconds: float = 3.0) -> None:
        if min_interval_seconds <= 0:
            raise ValueError("min_interval_seconds must be > 0")
        self._min_interval = float(min_interval_seconds)
        self._last: Dict[Tuple[Any, ...], float] = {}
        self._lock = asyncio.Lock()

    async def wait(self, key: Tuple[Any, ...]) -> None:
        while True:
            async with self._lock:
                now = time.monotonic()
                last = self._last.get(key)
                if last is None or now - last >= self._min_interval:
                    self._last[key] = now
                    return
                delay = self._min_interval - (now - last)
            await asyncio.sleep(delay)


class TTLCache:
    def __init__(self, ttl_seconds: float = 2.5) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be > 0")
        self.ttl = float(ttl_seconds)
        self._items: Dict[Tuple[Any, ...], Tuple[float, Any]] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: Tuple[Any, ...]) -> Optional[Any]:
        async with self._lock:
            item = self._items.get(key)
            if item is None:
                return None
            created, value = item
            if time.monotonic() - created >= self.ttl:
                self._items.pop(key, None)
                return None
            return value

    async def put(self, key: Tuple[Any, ...], value: Any) -> None:
        async with self._lock:
            self._items[key] = (time.monotonic(), value)

    async def clear(self) -> None:
        async with self._lock:
            self._items.clear()


class ExpiryResolver:
    def __init__(self, fetch_expiries: Callable[[UnderlyingRef], Awaitable[Sequence[str]]]) -> None:
        self._fetch_expiries = fetch_expiries
        self._cache: Dict[Tuple[str, int, str], Tuple[float, List[date]]] = {}
        self._ttl = 300.0
        self._lock = asyncio.Lock()

    async def active_expiries(self, underlying: UnderlyingRef, now: Optional[date] = None) -> List[date]:
        today = now or datetime.now(timezone.utc).date()
        key = (underlying.exchange_segment, underlying.security_id, underlying.symbol)
        async with self._lock:
            cached = self._cache.get(key)
            if cached and time.monotonic() - cached[0] < self._ttl:
                return [d for d in cached[1] if d >= today]
        raw = await self._fetch_expiries(underlying)
        parsed = sorted({date.fromisoformat(str(x)) for x in raw})
        async with self._lock:
            self._cache[key] = (time.monotonic(), parsed)
        return [d for d in parsed if d >= today]

    async def nearest(self, underlying: UnderlyingRef, now: Optional[date] = None) -> Optional[date]:
        expiries = await self.active_expiries(underlying, now=now)
        return expiries[0] if expiries else None


class OptionChainNormalizer:
    """Normalize Dhan option-chain JSON without inventing missing values."""

    @staticmethod
    def normalize(payload: Mapping[str, Any], request: ChainRequest) -> ChainSnapshot:
        data = payload.get("data") or {}
        if not isinstance(data, Mapping):
            raise ValueError("Invalid option-chain payload: data must be an object")
        raw_oc = data.get("oc") or {}
        if not isinstance(raw_oc, Mapping):
            raise ValueError("Invalid option-chain payload: oc must be an object")

        strikes: Dict[float, Dict[str, Dict[str, Any]]] = {}
        for strike_text, legs in raw_oc.items():
            try:
                strike = float(strike_text)
            except (TypeError, ValueError):
                continue
            if not isinstance(legs, Mapping):
                continue
            normalized_legs: Dict[str, Dict[str, Any]] = {}
            for option_type in ("ce", "pe"):
                leg = legs.get(option_type)
                if isinstance(leg, Mapping):
                    normalized_legs[option_type] = dict(leg)
            if normalized_legs:
                strikes[strike] = normalized_legs

        ltp = data.get("last_price")
        if ltp is not None:
            try:
                ltp = float(ltp)
                if ltp <= 0:
                    ltp = None
            except (TypeError, ValueError):
                ltp = None

        return ChainSnapshot(
            scanner_id=request.underlying.scanner_id,
            symbol=request.underlying.symbol,
            security_id=request.underlying.security_id,
            exchange_segment=request.underlying.exchange_segment,
            expiry=request.expiry,
            underlying_ltp=ltp,
            strikes=strikes,
            fetched_at=datetime.now(timezone.utc),
        )


class OptionChainCoordinator:
    """Coordinates expiry discovery, rate limiting, caching and normalization."""

    def __init__(
        self,
        fetch_expiries: Callable[[UnderlyingRef], Awaitable[Sequence[str]]],
        fetch_chain: Callable[[UnderlyingRef, date], Awaitable[Mapping[str, Any]]],
        *,
        request_interval_seconds: float = 3.0,
        cache_ttl_seconds: float = 2.5,
    ) -> None:
        self.resolver = ExpiryResolver(fetch_expiries)
        self.fetch_chain = fetch_chain
        self.gate = UniqueRequestGate(request_interval_seconds)
        self.cache = TTLCache(cache_ttl_seconds)
        self._inflight: Dict[Tuple[Any, ...], asyncio.Task[ChainSnapshot]] = {}
        self._inflight_lock = asyncio.Lock()

    @staticmethod
    def _key(underlying: UnderlyingRef, expiry: date) -> Tuple[Any, ...]:
        return (underlying.exchange_segment, underlying.security_id, underlying.symbol, expiry.isoformat())

    async def get_chain(self, underlying: UnderlyingRef, expiry: Optional[date] = None) -> ChainSnapshot:
        selected_expiry = expiry or await self.resolver.nearest(underlying)
        if selected_expiry is None:
            raise LookupError(f"No active option expiry for {underlying.symbol}")
        key = self._key(underlying, selected_expiry)

        cached = await self.cache.get(key)
        if cached is not None:
            return cached

        async with self._inflight_lock:
            existing = self._inflight.get(key)
            if existing is not None:
                return await existing
            task = asyncio.create_task(self._fetch_normalized(underlying, selected_expiry, key))
            self._inflight[key] = task

        try:
            return await task
        finally:
            async with self._inflight_lock:
                self._inflight.pop(key, None)

    async def _fetch_normalized(self, underlying: UnderlyingRef, expiry: date, key: Tuple[Any, ...]) -> ChainSnapshot:
        await self.gate.wait(key)
        payload = await self.fetch_chain(underlying, expiry)
        snapshot = OptionChainNormalizer.normalize(payload, ChainRequest(underlying, expiry))
        await self.cache.put(key, snapshot)
        return snapshot
