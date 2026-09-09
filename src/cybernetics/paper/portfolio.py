from dataclasses import dataclass

@dataclass(frozen=True)
class PortfolioSnapshot:
    realized_pnl: float
    fees: float
    open_positions: int

class PaperPortfolio:
    def __init__(self, broker):
        self.broker=broker
    def snapshot(self):
        return PortfolioSnapshot(
            sum(p.realized_pnl for p in self.broker.positions.values()),
            sum(f.fee for f in self.broker.fills),
            sum(1 for p in self.broker.positions.values() if p.quantity)
        )
