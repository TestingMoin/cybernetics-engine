from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Optional

class UniverseStatus(str, Enum):
    DISCOVERED = "DISCOVERED"
    VALIDATED = "VALIDATED"
    APPROVED = "APPROVED"
    ACTIVE = "ACTIVE"
    WARNING = "WARNING"
    NO_NEW_TRADES = "NO_NEW_TRADES"
    RETIRED = "RETIRED"

class InstrumentEligibility(str, Enum):
    NOT_ELIGIBLE = "NOT_ELIGIBLE"
    RESEARCH = "RESEARCH"
    PRODUCTION = "PRODUCTION"

@dataclass(frozen=True)
class GovernanceDecision:
    security_id: str
    status: UniverseStatus
    eligibility: InstrumentEligibility
    scanner_group_id: Optional[str]
    reason: str

@dataclass(frozen=True)
class GovernanceRecord:
    security_id: str
    exchange_segment: str
    symbol: str
    instrument_type: str
    scanner_group_id: Optional[str] = None
    status: UniverseStatus = UniverseStatus.DISCOVERED
    eligibility: InstrumentEligibility = InstrumentEligibility.NOT_ELIGIBLE
    options_available: bool = False
    lot_size: Optional[int] = None
    tick_size: Optional[float] = None

class UniverseGovernance:
    """
    Explicit governance state machine for the trading universe.

    The class deliberately separates:
      discovery -> validation -> approval -> activation
    from:
      warning -> no_new_trades -> retirement.

    It does not infer that a newly discovered derivative is production-ready.
    """
    def __init__(self):
        self._records: dict[str, GovernanceRecord] = {}

    def discover(self, record: GovernanceRecord) -> GovernanceDecision:
        if record.security_id in self._records:
            return self._decision(record.security_id, "already_discovered")
        if not record.symbol or not record.exchange_segment:
            raise ValueError("universe_record_identity_required")
        self._records[record.security_id] = record
        return self._decision(record.security_id, "discovered")

    def validate(self, security_id: str, *,
                 scanner_group_id: Optional[str],
                 options_available: bool,
                 lot_size: Optional[int],
                 tick_size: Optional[float]) -> GovernanceDecision:
        current = self._get(security_id)
        if lot_size is not None and lot_size <= 0:
            return self._set_blocked(current, "invalid_lot_size")
        if tick_size is not None and tick_size <= 0:
            return self._set_blocked(current, "invalid_tick_size")

        updated=GovernanceRecord(
            security_id=current.security_id,
            exchange_segment=current.exchange_segment,
            symbol=current.symbol,
            instrument_type=current.instrument_type,
            scanner_group_id=scanner_group_id,
            status=UniverseStatus.VALIDATED,
            eligibility=InstrumentEligibility.RESEARCH,
            options_available=options_available,
            lot_size=lot_size,
            tick_size=tick_size,
        )
        self._records[security_id]=updated
        return self._decision(security_id, "validated")

    def approve(self, security_id: str) -> GovernanceDecision:
        current=self._get(security_id)
        if current.status != UniverseStatus.VALIDATED:
            return self._decision(security_id,"approval_requires_validation")
        updated=GovernanceRecord(**{
            **current.__dict__,
            "status": UniverseStatus.APPROVED,
        })
        self._records[security_id]=updated
        return self._decision(security_id,"approved")

    def activate(self, security_id: str, *,
                 scanner_registry=None) -> GovernanceDecision:
        current=self._get(security_id)
        if current.status != UniverseStatus.APPROVED:
            return self._decision(security_id,"activation_requires_approval")
        if current.scanner_group_id and scanner_registry is not None:
            group=scanner_registry.get(current.scanner_group_id)
            if not group.enabled:
                return self._decision(security_id,"scanner_group_disabled")
        updated=GovernanceRecord(**{
            **current.__dict__,
            "status": UniverseStatus.ACTIVE,
            "eligibility": InstrumentEligibility.PRODUCTION,
        })
        self._records[security_id]=updated
        return self._decision(security_id,"activated")

    def warning(self, security_id: str, reason: str="governance_warning") -> GovernanceDecision:
        current=self._get(security_id)
        updated=GovernanceRecord(**{**current.__dict__,"status":UniverseStatus.WARNING,
                                    "eligibility":InstrumentEligibility.NOT_ELIGIBLE})
        self._records[security_id]=updated
        return self._decision(security_id,reason)

    def block_new_trades(self, security_id: str, reason: str="new_trades_blocked") -> GovernanceDecision:
        current=self._get(security_id)
        updated=GovernanceRecord(**{**current.__dict__,
                                    "status":UniverseStatus.NO_NEW_TRADES,
                                    "eligibility":InstrumentEligibility.NOT_ELIGIBLE})
        self._records[security_id]=updated
        return self._decision(security_id,reason)

    def retire(self, security_id: str, reason: str="retired") -> GovernanceDecision:
        current=self._get(security_id)
        updated=GovernanceRecord(**{**current.__dict__,
                                    "status":UniverseStatus.RETIRED,
                                    "eligibility":InstrumentEligibility.NOT_ELIGIBLE})
        self._records[security_id]=updated
        return self._decision(security_id,reason)

    def get(self, security_id: str) -> GovernanceRecord:
        return self._get(security_id)

    def production_eligible(self, security_id: str) -> bool:
        return self._get(security_id).eligibility == InstrumentEligibility.PRODUCTION

    def _get(self, security_id):
        try:
            return self._records[security_id]
        except KeyError:
            raise KeyError(f"universe_instrument_not_found:{security_id}")

    def _set_blocked(self,current,reason):
        updated=GovernanceRecord(**{
            **current.__dict__,
            "status":UniverseStatus.WARNING,
            "eligibility":InstrumentEligibility.NOT_ELIGIBLE,
        })
        self._records[current.security_id]=updated
        return self._decision(current.security_id,reason)

    def _decision(self, security_id, reason):
        r=self._get(security_id)
        return GovernanceDecision(
            security_id=r.security_id,
            status=r.status,
            eligibility=r.eligibility,
            scanner_group_id=r.scanner_group_id,
            reason=reason,
        )
