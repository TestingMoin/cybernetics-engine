from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Literal
import hashlib
import json
import time
import uuid

ProposalStatus = Literal["PROPOSED","UNDER_TEST","PASSED","REJECTED","APPROVED","RELEASED"]

@dataclass(frozen=True)
class AuditFinding:
    finding_id: str
    observed_at: float
    category: str
    severity: str
    summary: str
    evidence: dict[str, Any]
    source_version: str

@dataclass(frozen=True)
class ImprovementProposal:
    proposal_id: str
    created_at: float
    target_type: str
    target_id: str
    source_version: str
    proposed_change: dict[str, Any]
    rationale: str
    required_tests: tuple[str, ...]
    status: ProposalStatus = "PROPOSED"

    @property
    def proposal_hash(self) -> str:
        raw=json.dumps({
            "proposal_id":self.proposal_id,
            "target_type":self.target_type,
            "target_id":self.target_id,
            "source_version":self.source_version,
            "proposed_change":self.proposed_change,
            "rationale":self.rationale,
        },sort_keys=True,separators=(",",":"))
        return hashlib.sha256(raw.encode()).hexdigest()

class AuditAnalyzer:
    """
    Deterministic log analyzer used before any AI reasoning.
    It produces findings; it never changes a strategy.
    """
    def analyze(self, records: list[dict[str, Any]], source_version: str) -> list[AuditFinding]:
        findings=[]
        for r in records:
            if r.get("event_type")=="RECONCILIATION" and not r.get("matched",True):
                findings.append(AuditFinding(
                    str(uuid.uuid4()),time.time(),"RECONCILIATION","CRITICAL",
                    "Broker/internal reconciliation mismatch",r,source_version))
            if r.get("event_type")=="OPPORTUNITY_REJECTED" and r.get("repeated",False):
                findings.append(AuditFinding(
                    str(uuid.uuid4()),time.time(),"REJECTION_PATTERN","MEDIUM",
                    "Repeated opportunity rejection pattern",r,source_version))
            if r.get("event_type")=="DATA_QUALITY" and r.get("healthy") is False:
                findings.append(AuditFinding(
                    str(uuid.uuid4()),time.time(),"DATA_QUALITY","HIGH",
                    "Market-data quality degradation observed",r,source_version))
        return findings

class ProposalEngine:
    """Creates bounded change proposals; no filesystem writes and no deployment."""
    def propose(self, finding: AuditFinding, target_type: str, target_id: str,
                proposed_change: dict[str, Any], rationale: str,
                required_tests: tuple[str,...]) -> ImprovementProposal:
        return ImprovementProposal(
            proposal_id=str(uuid.uuid4()),
            created_at=time.time(),
            target_type=target_type,
            target_id=target_id,
            source_version=finding.source_version,
            proposed_change=proposed_change,
            rationale=rationale,
            required_tests=required_tests,
        )
