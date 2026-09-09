from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class BrokerOrder:
    order_id: str
    symbol: str
    side: str
    quantity: int
    filled_quantity: int
    avg_price: Optional[float]
    status: str

@dataclass(frozen=True)
class BrokerPosition:
    symbol: str
    quantity: int
    avg_price: float

@dataclass(frozen=True)
class InternalOrder:
    order_id: str
    symbol: str
    side: str
    quantity: int
    filled_quantity: int
    avg_price: Optional[float]
    status: str

@dataclass(frozen=True)
class InternalPosition:
    symbol: str
    quantity: int
    avg_price: float

@dataclass(frozen=True)
class ReconciliationIssue:
    kind: str
    severity: str
    key: str
    internal: object
    broker: object
    reason: str

@dataclass(frozen=True)
class ReconciliationReport:
    matched: bool
    issues: tuple[ReconciliationIssue, ...]
    no_new_trades: bool

class ReconciliationEngine:
    """Compare internal and broker state. Never mutates broker state."""
    def reconcile_orders(self, internal: list[InternalOrder], broker: list[BrokerOrder]) -> list[ReconciliationIssue]:
        a={x.order_id:x for x in internal}; b={x.order_id:x for x in broker}
        issues=[]
        for k in sorted(set(a)|set(b)):
            if k not in a:
                issues.append(ReconciliationIssue("UNEXPECTED_BROKER_ORDER","CRITICAL",k,None,b[k],"broker order absent internally"))
                continue
            if k not in b:
                issues.append(ReconciliationIssue("MISSING_BROKER_ORDER","HIGH",k,a[k],None,"internal order absent at broker"))
                continue
            i,r=a[k],b[k]
            if i.filled_quantity!=r.filled_quantity:
                issues.append(ReconciliationIssue("FILL_QUANTITY_MISMATCH","CRITICAL",k,i,r,"filled quantity differs"))
            if i.status!=r.status:
                issues.append(ReconciliationIssue("STATUS_MISMATCH","HIGH",k,i,r,"order status differs"))
            if i.symbol!=r.symbol or i.side!=r.side or i.quantity!=r.quantity:
                issues.append(ReconciliationIssue("ORDER_METADATA_MISMATCH","CRITICAL",k,i,r,"order identity fields differ"))
            if i.avg_price is not None and r.avg_price is not None and abs(i.avg_price-r.avg_price)>1e-9:
                issues.append(ReconciliationIssue("AVG_PRICE_MISMATCH","HIGH",k,i,r,"average fill price differs"))
        return issues

    def reconcile_positions(self, internal:list[InternalPosition], broker:list[BrokerPosition]) -> list[ReconciliationIssue]:
        a={x.symbol:x for x in internal}; b={x.symbol:x for x in broker}
        issues=[]
        for k in sorted(set(a)|set(b)):
            if k not in a:
                issues.append(ReconciliationIssue("UNEXPECTED_BROKER_POSITION","CRITICAL",k,None,b[k],"broker position absent internally"))
                continue
            if k not in b:
                issues.append(ReconciliationIssue("MISSING_BROKER_POSITION","CRITICAL",k,a[k],None,"internal position absent at broker"))
                continue
            i,r=a[k],b[k]
            if i.quantity!=r.quantity:
                issues.append(ReconciliationIssue("POSITION_QUANTITY_MISMATCH","CRITICAL",k,i,r,"position quantity differs"))
            if abs(i.avg_price-r.avg_price)>1e-9:
                issues.append(ReconciliationIssue("POSITION_PRICE_MISMATCH","HIGH",k,i,r,"average position price differs"))
        return issues

    def report(self, order_issues:list[ReconciliationIssue], position_issues:list[ReconciliationIssue]) -> ReconciliationReport:
        issues=tuple(order_issues+position_issues)
        return ReconciliationReport(matched=not issues, issues=issues, no_new_trades=bool(issues))
