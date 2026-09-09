from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass(frozen=True)
class GoldenContext:
    strategy_id: str
    signal_id: str
    timestamp: datetime
    month: int
    close: float
    direction: Optional[str]
    ema5: Optional[float]=None
    ema15: Optional[float]=None
    ema40: Optional[float]=None
    ema120: Optional[float]=None
    ema200: Optional[float]=None
    prev_ema5: Optional[float]=None
    prev_ema15: Optional[float]=None
    daily_ema5: Optional[float]=None
    daily_ema15: Optional[float]=None
    daily_ema40: Optional[float]=None
    daily_ema120: Optional[float]=None
    daily_ema200: Optional[float]=None
    daily_close: Optional[float]=None
    md_line: Optional[float]=None
    md_signal: Optional[float]=None
    higher_tf_pass: Optional[bool]=None
    allow_shorts: bool=False

@dataclass(frozen=True)
class GoldenDecision:
    strategy_id: str
    signal_id: str
    action: str
    rationale: str
    parity_fields: dict[str, object]
