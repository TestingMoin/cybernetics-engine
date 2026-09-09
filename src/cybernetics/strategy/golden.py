from __future__ import annotations
from .golden_models import GoldenContext, GoldenDecision

# These months reproduce the supplied Pine source inputs.
NIFTY_SENSEX_ALLOWED_MONTHS={4,5,6,7,8,10,11,12}
BANKNIFTY_ALLOWED_MONTHS={1,4,5,6,7,8,10,11,12}

def _cross_up(ctx):
    return (ctx.prev_ema5 is not None and ctx.prev_ema15 is not None and
            ctx.ema5 is not None and ctx.ema15 is not None and
            ctx.prev_ema5 <= ctx.prev_ema15 and ctx.ema5 > ctx.ema15)

def _cross_down(ctx):
    return (ctx.prev_ema5 is not None and ctx.prev_ema15 is not None and
            ctx.ema5 is not None and ctx.ema15 is not None and
            ctx.prev_ema5 >= ctx.prev_ema15 and ctx.ema5 < ctx.ema15)

class NiftySensexGolden:
    strategy_id="GOLDEN-NIFTY-SENSEX"
    version="1.0.0-reproduction-target"

    def evaluate(self, ctx: GoldenContext) -> GoldenDecision:
        if ctx.month not in NIFTY_SENSEX_ALLOWED_MONTHS:
            return GoldenDecision(self.strategy_id,ctx.signal_id,"NO_ACTION",
                                  "month_not_allowed",{"month":ctx.month})
        daily_up=(ctx.daily_ema5 is not None and ctx.daily_ema15 is not None
                  and ctx.daily_ema5>ctx.daily_ema15)
        daily_down=(ctx.daily_ema5 is not None and ctx.daily_ema15 is not None
                    and ctx.daily_ema5<ctx.daily_ema15)
        long_ok=ctx.direction=="BUY" and _cross_up(ctx) and daily_up
        short_ok=ctx.direction=="SELL" and _cross_down(ctx) and daily_down and ctx.allow_shorts
        if long_ok:
            return GoldenDecision(self.strategy_id,ctx.signal_id,"ENTER_LONG",
                                  "ema5_cross_up_and_daily_up_and_month_allowed",{
                                    "cross_up":True,"daily_up":True,"month_allowed":True})
        if short_ok:
            return GoldenDecision(self.strategy_id,ctx.signal_id,"ENTER_SHORT",
                                  "ema5_cross_down_and_daily_down_and_shorts_enabled",{
                                    "cross_down":True,"daily_down":True,"month_allowed":True})
        return GoldenDecision(self.strategy_id,ctx.signal_id,"NO_ACTION",
                              "entry_conditions_not_met",{
                                  "cross_up":_cross_up(ctx),"cross_down":_cross_down(ctx),
                                  "daily_up":daily_up,"daily_down":daily_down,
                                  "allow_shorts":ctx.allow_shorts})

class BankNiftyGolden:
    strategy_id="GOLDEN-BANKNIFTY"
    version="1.0.0-reproduction-target"

    def evaluate(self, ctx: GoldenContext) -> GoldenDecision:
        if ctx.month not in BANKNIFTY_ALLOWED_MONTHS:
            return GoldenDecision(self.strategy_id,ctx.signal_id,"NO_ACTION",
                                  "month_not_allowed",{"month":ctx.month})
        daily_up=(ctx.daily_ema40 is not None and ctx.daily_ema120 is not None
                  and ctx.daily_ema200 is not None and ctx.daily_close is not None
                  and ctx.daily_ema40>ctx.daily_ema120 and ctx.daily_close>ctx.daily_ema200)
        tf_up=(ctx.ema40 is not None and ctx.ema120 is not None and ctx.ema200 is not None
               and ctx.close>ctx.ema200 and ctx.ema40>ctx.ema120)
        momentum=(ctx.md_line is not None and ctx.md_signal is not None and
                  ctx.md_line>ctx.md_signal)
        ht_ok=(ctx.higher_tf_pass is not False)
        buy_ok=(ctx.direction=="BUY" and daily_up and tf_up and momentum and ht_ok)
        if buy_ok:
            return GoldenDecision(self.strategy_id,ctx.signal_id,"ENTER_LONG",
                                  "daily_gate_and_timeframe_trend_and_momentum",{
                                      "daily_up":daily_up,"timeframe_up":tf_up,
                                      "momentum_up":momentum,"higher_tf_pass":ht_ok,
                                      "month_allowed":True})
        # Pine source defines sellSignal as a state/exit condition rather than
        # a separate short-entry branch. Preserve that distinction here.
        exit_long=(ctx.direction=="SELL" or not daily_up or not tf_up)
        if exit_long:
            return GoldenDecision(self.strategy_id,ctx.signal_id,"EXIT_LONG",
                                  "sell_signal_or_daily_or_timeframe_trend_failed",{
                                      "daily_up":daily_up,"timeframe_up":tf_up,
                                      "momentum_up":momentum})
        return GoldenDecision(self.strategy_id,ctx.signal_id,"NO_ACTION",
                              "entry_conditions_not_met",{
                                  "daily_up":daily_up,"timeframe_up":tf_up,
                                  "momentum_up":momentum,"higher_tf_pass":ht_ok})

def golden_registry():
    return {NiftySensexGolden.strategy_id:NiftySensexGolden(),
            BankNiftyGolden.strategy_id:BankNiftyGolden()}
