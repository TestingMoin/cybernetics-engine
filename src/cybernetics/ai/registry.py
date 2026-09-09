from __future__ import annotations
from dataclasses import dataclass
from .auditor import ImprovementProposal

@dataclass(frozen=True)
class ProposalRecord:
    proposal: ImprovementProposal
    validation_status: str
    approval_status: str = "PENDING"

class ProposalRegistry:
    def __init__(self):
        self.records: dict[str, ProposalRecord] = {}

    def add(self, proposal: ImprovementProposal) -> None:
        if proposal.proposal_id in self.records:
            raise ValueError("duplicate proposal")
        self.records[proposal.proposal_id]=ProposalRecord(proposal,"NOT_RUN")

    def set_validation(self, proposal_id: str, status: str) -> None:
        old=self.records[proposal_id]
        self.records[proposal_id]=ProposalRecord(old.proposal,status,old.approval_status)

    def approve(self, proposal_id: str, approved_by: str) -> None:
        if not approved_by:
            raise ValueError("approved_by required")
        old=self.records[proposal_id]
        self.records[proposal_id]=ProposalRecord(old.proposal,old.validation_status,approved_by)

    def get(self, proposal_id: str) -> ProposalRecord:
        return self.records[proposal_id]
