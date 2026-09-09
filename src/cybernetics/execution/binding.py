from dataclasses import dataclass, field
from typing import Optional, Any
from .instrument import TradeInstrument
from .intent import ExecutionIntent, ExecutionAction, OrderType

@dataclass(frozen=True)
class BoundExecutionInstruction:
    intent_id:str; trade_id:str; strategy_id:str; strategy_version:str; signal_id:str
    exchange_segment:str; security_id:str; symbol:str
    action:ExecutionAction; order_type:OrderType; quantity:int
    lot_size:int; tick_size:float; contract_multiplier:float
    expiry:Optional[object]=None; strike:Optional[float]=None; option_type:Optional[object]=None
    limit_price:Optional[float]=None; product_type:str="INTRADAY"; validity:str="DAY"
    metadata:dict[str,Any]=field(default_factory=dict)

class ExecutionIntentInstrumentBinder:
    def bind(self,intent,instrument):
        if instrument.symbol.upper()!=intent.underlying_key.upper():
            raise ValueError("intent_instrument_symbol_mismatch")
        if intent.quantity<=0: raise ValueError("bound_quantity_must_be_positive")
        if intent.quantity % instrument.lot_size: raise ValueError("bound_quantity_not_lot_aligned")
        if intent.order_type==OrderType.LIMIT:
            p=intent.limit_price; ts=instrument.tick_size
            if p is None or p<=0: raise ValueError("bound_limit_price_invalid")
            if abs(p-round(p/ts)*ts)>max(1e-9,ts*1e-9):
                raise ValueError("limit_price_not_on_tick_grid")
        return BoundExecutionInstruction(
            intent.intent_id,intent.trade_id,intent.strategy_id,intent.strategy_version,intent.signal_id,
            instrument.exchange_segment,instrument.security_id,instrument.symbol,intent.action,intent.order_type,
            intent.quantity,instrument.lot_size,instrument.tick_size,instrument.contract_multiplier,
            instrument.expiry,instrument.strike,instrument.option_type,intent.limit_price,intent.product_type,
            intent.validity,dict(intent.metadata))
