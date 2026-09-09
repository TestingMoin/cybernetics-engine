from dataclasses import dataclass

@dataclass(frozen=True)
class ConfluencePolicy:
    policy_id: str
    strategy_id: str
    minimum_score: float
    required_evidence: tuple[str, ...] = ()
    allowed_regimes: tuple[str, ...] = ()
    allow_options_context: bool = True
    allow_iceberg_context: bool = True
    allow_gap_context: bool = True
    allow_gann_context: bool = True
    allow_ichimoku_context: bool = True

DEFAULT_GOLDEN_POLICIES = (
    ConfluencePolicy("POL-NIFTY-GOLDEN","GOLDEN_NIFTY_SENSEX_EMA",0.60,
                     ("strategy",),("TREND_UP","TREND_DOWN","LOW_VOL","HIGH_VOL")),
    ConfluencePolicy("POL-BANKNIFTY-GOLDEN","GOLDEN_BANKNIFTY_MULTIFACTOR",0.60,
                     ("strategy",),("TREND_UP","TREND_DOWN","LOW_VOL","HIGH_VOL")),
)
