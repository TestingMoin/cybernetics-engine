from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class AIControlPolicy:
    allow_auto_strategy_edit: bool = False
    allow_auto_deployment: bool = False
    allow_auto_live_authorization: bool = False
    allow_ai_order_generation: bool = False
    require_human_approval: bool = True
    require_golden_regression: bool = True
    require_oos: bool = True
    require_paper: bool = True

DEFAULT_AI_POLICY = AIControlPolicy()
