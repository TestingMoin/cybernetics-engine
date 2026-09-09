from __future__ import annotations
from dataclasses import dataclass
from typing import Callable
from .auditor import ImprovementProposal

@dataclass(frozen=True)
class ValidationResult:
    proposal_id: str
    tests_passed: bool
    backtest_passed: bool
    out_of_sample_passed: bool
    paper_passed: bool
    regression_passed: bool
    reasons: tuple[str,...]

@dataclass(frozen=True)
class ApprovalResult:
    approved: bool
    reason: str

class ImprovementGate:
    """
    Enforces staged validation and explicit approval.
    No automatic production release is possible through this class.
    """
    def evaluate(self, proposal: ImprovementProposal, *,
                 run_tests: Callable[[],bool],
                 run_backtest: Callable[[],bool],
                 run_oos: Callable[[],bool],
                 run_paper: Callable[[],bool],
                 run_regression: Callable[[],bool]) -> ValidationResult:
        checks=[
            ("tests",run_tests),("backtest",run_backtest),
            ("out_of_sample",run_oos),("paper",run_paper),
            ("regression",run_regression)
        ]
        reasons=[]
        values={}
        for name,fn in checks:
            try:
                ok=bool(fn())
            except Exception as exc:
                ok=False
                reasons.append(f"{name}:exception:{exc}")
            values[name]=ok
            if not ok and not any(x.startswith(name+":") for x in reasons):
                reasons.append(f"{name}:failed")
                break
        passed=all(values.get(name,False) for name,_ in checks)
        return ValidationResult(proposal.proposal_id,values.get("tests",False),
                                values.get("backtest",False),values.get("out_of_sample",False),
                                values.get("paper",False),values.get("regression",False),
                                tuple(reasons))

    def require_human_approval(self, validation: ValidationResult, *,
                               approved_by: str | None = None) -> ApprovalResult:
        if not validation.tests_passed or not validation.backtest_passed:
            return ApprovalResult(False,"mandatory_validation_failed")
        if not validation.out_of_sample_passed or not validation.paper_passed:
            return ApprovalResult(False,"staged_validation_incomplete")
        if not validation.regression_passed:
            return ApprovalResult(False,"regression_failed")
        if not approved_by:
            return ApprovalResult(False,"explicit_human_approval_required")
        return ApprovalResult(True,f"approved_by:{approved_by}")
