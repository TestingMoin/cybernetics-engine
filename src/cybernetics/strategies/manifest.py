from __future__ import annotations
from dataclasses import dataclass
from typing import Literal

Status=Literal["GOLDEN","VALIDATED","RESEARCH","EXPERIMENTAL","UNSUPPORTED"]

@dataclass(frozen=True)
class StrategyManifest:
    strategy_id:str
    name:str
    status:Status
    allowed_underlyings:tuple[str,...]
    timeframes:tuple[str,...]
    source_note:str

def golden_manifest()->tuple[StrategyManifest,...]:
    return (
        StrategyManifest("GOLDEN_NIFTY_SENSEX_EMA","Optimized Intraday Strategy (SL/TP/Shorts)",
                         "GOLDEN",("NIFTY","SENSEX"),("1m","5m","15m","30m","60m","240m","D"),
                         "Exact reproduction target from attached Pine source."),
        StrategyManifest("GOLDEN_BANKNIFTY_MULTIFACTOR","BankNifty Intraday with Daily Trend Filter",
                         "GOLDEN",("BANKNIFTY",),("1m","5m","15m","30m","60m","240m","D"),
                         "Exact reproduction target from attached Pine source."),
        StrategyManifest("RESEARCH_SMART_RENKO","Smart Renko Engine (Renko-Aligned)",
                         "RESEARCH",("NIFTY","SENSEX","BANKNIFTY"),("1m","5m","15m"),
                         "Research engine; retain independently until parity validation."),
        StrategyManifest("RESEARCH_SWING_FORECAST","Swing Structure Forecast",
                         "RESEARCH",("NIFTY","SENSEX","BANKNIFTY"),("15m","30m","60m","D"),
                         "Research/forecast engine; not an automatic entry strategy."),
    )
