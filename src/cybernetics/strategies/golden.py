from __future__ import annotations
from dataclasses import dataclass
from .models import StrategyContext, StrategyDecision

@dataclass(frozen=True)
class NiftySensexGoldenConfig:
    fast_len: int = 5
    slow_len: int = 15
    sl_percent: float = 0.5
    tp_percent: float = 1.0
    allow_short: bool = True
    use_trailing: bool = False
    trail_points: float = 50.0
    trail_offset: float = 20.0
    allowed_months: tuple[int, ...] = (4,5,6,7,8,10,11,12)

class NiftySensexGoldenStrategy:
    strategy_id = "GOLDEN_NIFTY_SENSEX_EMA"

    def __init__(self, config: NiftySensexGoldenConfig | None = None):
        self.config = config or NiftySensexGoldenConfig()

    def decide(self, ctx: StrategyContext, *, fast_ema: float | None,
               slow_ema: float | None, prev_fast_ema: float | None,
               prev_slow_ema: float | None, daily_fast: float | None,
               daily_slow: float | None, bar_high: float | None = None,
               bar_low: float | None = None) -> StrategyDecision:
        c=self.config
        if None in (fast_ema, slow_ema, prev_fast_ema, prev_slow_ema, daily_fast, daily_slow):
            return StrategyDecision(self.strategy_id,"WAIT","insufficient_indicator_history")
        daily_up = daily_fast > daily_slow
        daily_down = daily_fast < daily_slow
        buy_cross = prev_fast_ema <= prev_slow_ema and fast_ema > slow_ema
        sell_cross = prev_fast_ema >= prev_slow_ema and fast_ema < slow_ema
        long_allowed = daily_up and ctx.month in c.allowed_months
        short_allowed = daily_down and c.allow_short

        if ctx.position_side == "FLAT":
            if buy_cross and long_allowed:
                stop=ctx.close*(1-c.sl_percent/100)
                target=ctx.close*(1+c.tp_percent/100)
                return StrategyDecision(self.strategy_id,"ENTER_LONG","daily_up_and_ema_bull_cross","LONG",stop,target,
                                         {"allowed_month":True})
            if sell_cross and short_allowed:
                stop=ctx.close*(1+c.sl_percent/100)
                target=ctx.close*(1-c.tp_percent/100)
                return StrategyDecision(self.strategy_id,"ENTER_SHORT","daily_down_and_ema_bear_cross","SHORT",stop,target,
                                         {"allowed_month":ctx.month in c.allowed_months})
            return StrategyDecision(self.strategy_id,"WAIT","no_entry")

        if ctx.position_side == "LONG":
            if not daily_up or sell_cross:
                return StrategyDecision(self.strategy_id,"EXIT","trend_or_signal_exit","LONG")
            return StrategyDecision(self.strategy_id,"HOLD","long_position_maintained","LONG")

        if ctx.position_side == "SHORT":
            if not daily_down or buy_cross:
                return StrategyDecision(self.strategy_id,"EXIT","trend_or_signal_exit","SHORT")
            return StrategyDecision(self.strategy_id,"HOLD","short_position_maintained","SHORT")

        return StrategyDecision(self.strategy_id,"WAIT","unknown_position_state")

@dataclass(frozen=True)
class BankNiftyGoldenConfig:
    allowed_months: tuple[int, ...] = (1,4,5,6,7,8,10,11,12)
    use_4h: bool=False
    use_1h: bool=False
    use_30m: bool=False
    use_15m: bool=False
    use_5m: bool=False

class BankNiftyGoldenStrategy:
    strategy_id = "GOLDEN_BANKNIFTY_MULTIFACTOR"

    def __init__(self, config: BankNiftyGoldenConfig | None = None):
        self.config=config or BankNiftyGoldenConfig()

    def decide(self, ctx: StrategyContext, *, daily_ema40: float | None,
               daily_ema120: float | None, daily_ema200: float | None,
               tf_filters_up: bool, ema40: float | None, ema120: float | None,
               ema200: float | None, md_line: float | None,
               md_signal: float | None) -> StrategyDecision:
        c=self.config
        vals=(daily_ema40,daily_ema120,daily_ema200,ema40,ema120,ema200,md_line,md_signal)
        if any(v is None for v in vals):
            return StrategyDecision(self.strategy_id,"WAIT","insufficient_indicator_history")
        daily_up=(ctx.close > daily_ema200) and (daily_ema40 > daily_ema120)
        trend_up=ctx.close > ema200
        base_up=ema40 > ema120
        momentum_up=md_line > md_signal
        buy_signal=trend_up and base_up and momentum_up
        sell_signal=not buy_signal
        long_allowed=daily_up and tf_filters_up and ctx.month in c.allowed_months

        if ctx.position_side=="FLAT" and buy_signal and long_allowed:
            return StrategyDecision(self.strategy_id,"ENTER_LONG","daily_multifactor_and_intraday_confirmation","LONG",
                                    metadata={"daily_up":daily_up,"trend_up":trend_up,"base_up":base_up,"momentum_up":momentum_up})
        if ctx.position_side=="LONG":
            if sell_signal:
                return StrategyDecision(self.strategy_id,"EXIT","intraday_multifactor_lost","LONG")
            if not daily_up:
                return StrategyDecision(self.strategy_id,"EXIT","daily_trend_down","LONG")
            return StrategyDecision(self.strategy_id,"HOLD","long_position_maintained","LONG")
        return StrategyDecision(self.strategy_id,"WAIT","no_entry")
