from dataclasses import dataclass

@dataclass(frozen=True)
class IntegrationResult:
    delivered: bool
    indicators_processed: bool
    signal_registered: bool
    reason: str
    signal_id: str | None = None

class MarketToSignalPipeline:
    """
    Minimal deterministic bridge for this milestone.
    Dependencies are injected so the production modules from prior chunks can
    replace these boundaries without changing the signal/execution separation.
    """
    def __init__(self, router, runtimes, indicator_adapter, signals, signal_factory=None):
        self.router=router
        self.runtimes=runtimes
        self.indicator_adapter=indicator_adapter
        self.signals=signals
        self.signal_factory=signal_factory
        self._states={}

    def process(self,event):
        decision=self.router.route(event)
        if not decision.delivered:
            return IntegrationResult(False,False,False,decision.reason)
        runtime_key=decision.runtime_key
        runtime=self.runtimes.get(runtime_key)
        p=event.payload
        for k in ("high","low","close"):
            if k not in p:
                return IntegrationResult(True,False,False,"missing_ohlcv_for_indicator")
        state=self._states.setdefault(
            runtime_key,
            self.indicator_adapter.runtime(runtime_key.underlying_key, runtime_key.timeframe)
        )
        snap=self.indicator_adapter.process(
            state, timestamp=event.timestamp,
            high=float(p["high"]), low=float(p["low"]),
            close=float(p["close"]), volume=float(p.get("volume",0))
        )
        runtime.state_data["last_indicator_values"]=snap.values
        runtime.state_data["last_indicator_ready"]=snap.ready

        if self.signal_factory is None:
            return IntegrationResult(True,True,False,"indicators_processed_no_signal_factory")
        signal=self.signal_factory(event,runtime_key,snap.values)
        if signal is None:
            return IntegrationResult(True,True,False,"no_signal")
        self.signals.register(signal)
        runtime.update(signal_delta=1)
        return IntegrationResult(True,True,True,"signal_registered",signal.signal_id)
