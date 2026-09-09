from __future__ import annotations
from dataclasses import dataclass
from .models import StrategyContext, StrategyDecision

@dataclass(frozen=True)
class SmartRenkoConfig:
    fast_len:int=5
    slow_len:int=15
    adx_threshold:float=20.0
    use_volume_filter:bool=True
    use_supertrend_filter:bool=True
    trap_session:bool=True

class SmartRenkoStrategy:
    strategy_id="RESEARCH_SMART_RENKO"

    def __init__(self, config:SmartRenkoConfig|None=None):
        self.config=config or SmartRenkoConfig()

    def decide(self, ctx:StrategyContext, *, fast_ema:float|None, slow_ema:float|None,
               prev_fast_ema:float|None, prev_slow_ema:float|None, adx:float|None,
               volume_ok:bool, supertrend_up:bool, in_trap:bool)->StrategyDecision:
        if any(v is None for v in (fast_ema,slow_ema,prev_fast_ema,prev_slow_ema,adx)):
            return StrategyDecision(self.strategy_id,"WAIT","insufficient_indicator_history")
        cross_up=prev_fast_ema<=prev_slow_ema and fast_ema>slow_ema
        cross_down=prev_fast_ema>=prev_slow_ema and fast_ema<slow_ema
        filters=(adx>=self.config.adx_threshold and
                 (not self.config.use_volume_filter or volume_ok) and
                 (not self.config.use_supertrend_filter or supertrend_up) and
                 (not self.config.trap_session or not in_trap))
        if ctx.position_side=="FLAT" and cross_up and filters:
            return StrategyDecision(self.strategy_id,"ENTER_LONG","renko_ema_cross_with_filters","LONG")
        if ctx.position_side=="FLAT" and cross_down and filters and (not self.config.use_supertrend_filter or not supertrend_up):
            return StrategyDecision(self.strategy_id,"ENTER_SHORT","renko_ema_cross_with_filters","SHORT")
        if ctx.position_side=="LONG" and cross_down:
            return StrategyDecision(self.strategy_id,"EXIT","opposite_renko_signal","LONG")
        if ctx.position_side=="SHORT" and cross_up:
            return StrategyDecision(self.strategy_id,"EXIT","opposite_renko_signal","SHORT")
        return StrategyDecision(self.strategy_id,"WAIT","no_action")

@dataclass(frozen=True)
class SwingForecastConfig:
    samples:int=10
    method:str="Weighted"
    forward_bars:int=3
    fib_levels:tuple[float,...]=(1.0,1.272,1.618)

class SwingStructureForecast:
    strategy_id="RESEARCH_SWING_FORECAST"

    def __init__(self, config:SwingForecastConfig|None=None):
        self.config=config or SwingForecastConfig()

    def forecast(self, swings_pct:list[float], durations:list[float], origin_price:float, bearish:bool):
        if len(swings_pct)<2 or len(swings_pct)!=len(durations):
            return None
        p=swings_pct[-self.config.samples:]
        d=durations[-self.config.samples:]
        if self.config.method=="Median":
            f_pct=sorted(p)[len(p)//2]
            f_bars=sorted(d)[len(d)//2]
        elif self.config.method=="Average":
            f_pct=sum(p)/len(p); f_bars=sum(d)/len(d)
        else:
            weights=list(range(1,len(p)+1))
            f_pct=sum(x*w for x,w in zip(p,weights))/sum(weights)
            f_bars=sum(x*w for x,w in zip(d,weights))/sum(weights)
        target=origin_price*(1-f_pct/100 if bearish else 1+f_pct/100)
        return {"forecast_pct":f_pct,"forecast_bars":f_bars,"target":target,
                "fib_targets":[origin_price + (target-origin_price)*r for r in self.config.fib_levels]}
