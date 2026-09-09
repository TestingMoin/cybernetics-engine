from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from typing import Optional, Any

class RiskAction(str, Enum):
    ENTER_LONG="ENTER_LONG"; ENTER_SHORT="ENTER_SHORT"
    EXIT_LONG="EXIT_LONG"; EXIT_SHORT="EXIT_SHORT"
    HOLD="HOLD"; NO_ACTION="NO_ACTION"

@dataclass(frozen=True)
class StrategyRiskRequest:
    request_id:str; strategy_id:str; strategy_version:str; signal_id:str
    trade_id:str; underlying_key:str; timeframe:str; action:RiskAction
    timestamp:datetime
    entry_reference_price:Optional[float]=None
    stop_reference_price:Optional[float]=None
    target_reference_price:Optional[float]=None
    metadata:dict[str,Any]=field(default_factory=dict)
    def __post_init__(self):
        if not self.request_id or not self.strategy_id or not self.strategy_version:
            raise ValueError("risk_request_identity_required")
        if not self.signal_id or not self.trade_id or not self.underlying_key:
            raise ValueError("risk_request_context_required")
        if self.entry_reference_price is not None and self.entry_reference_price<=0:
            raise ValueError("entry_reference_price_must_be_positive")
        if self.stop_reference_price is not None and self.stop_reference_price<=0:
            raise ValueError("stop_reference_price_must_be_positive")
        if self.target_reference_price is not None and self.target_reference_price<=0:
            raise ValueError("target_reference_price_must_be_positive")

@dataclass(frozen=True)
class RiskHandoffResult:
    accepted:bool; reason:str; request:StrategyRiskRequest

class StrategyRiskHandoff:
    def create_request(self, *, strategy_id, strategy_version, signal_id, trade_id,
                       underlying_key, timeframe, action, timestamp,
                       entry_reference_price=None, stop_reference_price=None,
                       target_reference_price=None, metadata=None):
        try: normalized=action if isinstance(action,RiskAction) else RiskAction(str(action).upper())
        except ValueError:
            req=StrategyRiskRequest("INVALID",strategy_id,strategy_version,signal_id or "INVALID",
                trade_id or "INVALID",underlying_key or "INVALID",timeframe or "INVALID",
                RiskAction.NO_ACTION,timestamp,metadata=metadata or {})
            return RiskHandoffResult(False,"unsupported_risk_action",req)
        req=StrategyRiskRequest(
            f"{strategy_id}:{trade_id}:{signal_id}:{normalized.value}",
            strategy_id,strategy_version,signal_id,trade_id,underlying_key,timeframe,
            normalized,timestamp,entry_reference_price,stop_reference_price,
            target_reference_price,metadata or {})
        if normalized in {RiskAction.HOLD,RiskAction.NO_ACTION}:
            return RiskHandoffResult(False,"non_executable_strategy_action",req)
        return RiskHandoffResult(True,"risk_request_created",req)
