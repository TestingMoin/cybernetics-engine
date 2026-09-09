from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Optional
import time, uuid, statistics

@dataclass(frozen=True)
class DepthLevel:
    price: float
    quantity: float

@dataclass(frozen=True)
class MarketObservation:
    ts: float
    exchange: str
    scanner_group: str
    asset: str
    instrument: str
    underlying: str
    price: float
    volume: float
    depth_bid: tuple[DepthLevel, ...] = ()
    depth_ask: tuple[DepthLevel, ...] = ()
    oi: Optional[float] = None
    iv: Optional[float] = None
    timeframe: str = "1m"

@dataclass(frozen=True)
class IcebergEvent:
    event_id: str
    timestamp: float
    exchange: str
    scanner_group: str
    asset: str
    instrument: str
    underlying: str
    direction: str
    price_zone: tuple[float, float]
    observed_volume: float
    relative_volume: Optional[float]
    depth_signal: float
    trade_cluster_score: float
    absorption_score: float
    replenishment_score: float
    oi_confirmation: Optional[float]
    volatility_context: Optional[float]
    regime: Optional[str]
    confidence: float
    evidence: tuple[str, ...]
    invalidations: tuple[str, ...]
    expiry: Optional[float]
    ttl_seconds: float

    def to_dict(self) -> dict:
        return asdict(self)

class IcebergDetector:
    """
    Observable iceberg-like/absorption detector.
    It never asserts knowledge of hidden orders and never emits broker orders.
    """

    def __init__(
        self,
        *,
        relative_volume_threshold: float = 2.0,
        absorption_threshold: float = 0.60,
        replenishment_threshold: float = 0.60,
        confidence_threshold: float = 0.70,
        ttl_seconds: float = 120.0,
    ):
        self.relative_volume_threshold = relative_volume_threshold
        self.absorption_threshold = absorption_threshold
        self.replenishment_threshold = replenishment_threshold
        self.confidence_threshold = confidence_threshold
        self.ttl_seconds = ttl_seconds

    @staticmethod
    def _depth_signal(obs: MarketObservation, direction: str) -> float:
        levels = obs.depth_bid if direction == "BUY" else obs.depth_ask
        if not levels:
            return 0.0
        qty = sum(max(0.0, x.quantity) for x in levels)
        if qty <= 0:
            return 0.0
        top = max(0.0, levels[0].quantity)
        return min(1.0, top / qty)

    @staticmethod
    def _relative_volume(observed: float, baseline: Optional[list[float]]) -> Optional[float]:
        if not baseline:
            return None
        positive = [x for x in baseline if x > 0]
        if not positive:
            return None
        med = statistics.median(positive)
        return observed / med if med > 0 else None

    def detect(
        self,
        obs: MarketObservation,
        *,
        prior_traded_volumes: Optional[list[float]] = None,
        repeated_replenishment: float = 0.0,
        price_stability_score: float = 0.0,
        trade_cluster_score: float = 0.0,
        oi_confirmation: Optional[float] = None,
        volatility_context: Optional[float] = None,
        regime: Optional[str] = None,
    ) -> Optional[IcebergEvent]:
        """Detect observable absorption/iceberg-like activity only; no hidden-order claim."""

        if obs.price <= 0 or obs.volume < 0:
            return None

        rv = self._relative_volume(obs.volume, prior_traded_volumes)
        volume_score = 0.0 if rv is None else min(1.0, rv / max(1.0, self.relative_volume_threshold))
        direction = "BUY" if price_stability_score >= 0.5 else "SELL"
        depth = self._depth_signal(obs, direction)

        # Absorption is intentionally a composite of observable evidence.
        absorption = min(1.0, 0.45 * price_stability_score + 0.35 * volume_score + 0.20 * depth)
        replenishment = min(1.0, max(0.0, repeated_replenishment))
        cluster = min(1.0, max(0.0, trade_cluster_score))

        oi_score = None if oi_confirmation is None else min(1.0, abs(oi_confirmation))
        components = [absorption, replenishment, cluster, depth]
        if oi_score is not None:
            components.append(oi_score)

        confidence = sum(components) / len(components)
        evidence = []
        if rv is not None and rv >= self.relative_volume_threshold:
            evidence.append("relative_volume_anomaly")
        if price_stability_score >= 0.5 and obs.volume > 0:
            evidence.append("price_volume_absorption")
        if replenishment >= self.replenishment_threshold:
            evidence.append("repeated_replenishment")
        if depth > 0:
            evidence.append("visible_depth_signal")
        if cluster >= 0.5:
            evidence.append("trade_cluster")
        if oi_score is not None and oi_score >= 0.5:
            evidence.append("oi_confirmation")

        invalidations = ["price_zone_break", "data_quality_failure", "event_ttl_expired"]
        if confidence < self.confidence_threshold or absorption < self.absorption_threshold:
            return None

        zone = (obs.price, obs.price)
        now = time.time()
        return IcebergEvent(
            event_id=str(uuid.uuid4()),
            timestamp=obs.ts,
            exchange=obs.exchange,
            scanner_group=obs.scanner_group,
            asset=obs.asset,
            instrument=obs.instrument,
            underlying=obs.underlying,
            direction=direction,
            price_zone=zone,
            observed_volume=obs.volume,
            relative_volume=rv,
            depth_signal=depth,
            trade_cluster_score=cluster,
            absorption_score=absorption,
            replenishment_score=replenishment,
            oi_confirmation=oi_confirmation,
            volatility_context=volatility_context,
            regime=regime,
            confidence=confidence,
            evidence=tuple(evidence),
            invalidations=tuple(invalidations),
            expiry=now + self.ttl_seconds,
            ttl_seconds=self.ttl_seconds,
        )
