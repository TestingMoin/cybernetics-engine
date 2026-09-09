from .registry import IndicatorRegistry, IndicatorSpec, IndicatorTier
from .library import ema,sma,wma,rsi,atr,bollinger_bands,roc,highest,lowest,stochastic_k,stochastic_d,macd,adx,obv,vwap

def build_standard_registry()->IndicatorRegistry:
    r=IndicatorRegistry()
    specs=[
        ("EMA","1.0.0","TREND",IndicatorTier.CORE,ema,"Exponential moving average"),
        ("SMA","1.0.0","TREND",IndicatorTier.CORE,sma,"Simple moving average"),
        ("WMA","1.0.0","TREND",IndicatorTier.CORE,wma,"Weighted moving average"),
        ("RSI","1.0.0","MOMENTUM",IndicatorTier.CORE,rsi,"Relative strength index"),
        ("ATR","1.0.0","VOLATILITY",IndicatorTier.CORE,atr,"Average true range"),
        ("BB","1.0.0","VOLATILITY",IndicatorTier.CORE,bollinger_bands,"Bollinger bands"),
        ("ROC","1.0.0","MOMENTUM",IndicatorTier.CORE,roc,"Rate of change"),
        ("HIGHEST","1.0.0","LEVELS",IndicatorTier.CORE,highest,"Rolling high"),
        ("LOWEST","1.0.0","LEVELS",IndicatorTier.CORE,lowest,"Rolling low"),
        ("STOCH_K","1.0.0","MOMENTUM",IndicatorTier.ADVANCED,stochastic_k,"Stochastic %K"),
        ("STOCH_D","1.0.0","MOMENTUM",IndicatorTier.ADVANCED,stochastic_d,"Stochastic %D"),
        ("MACD","1.0.0","MOMENTUM",IndicatorTier.ADVANCED,macd,"Moving average convergence divergence"),
        ("ADX","1.0.0","TREND_STRENGTH",IndicatorTier.ADVANCED,adx,"Average directional index"),
        ("OBV","1.0.0","VOLUME",IndicatorTier.ADVANCED,obv,"On-balance volume"),
        ("VWAP","1.0.0","VOLUME_PRICE",IndicatorTier.ADVANCED,vwap,"Volume weighted average price"),
    ]
    for s in specs:r.register(IndicatorSpec(*s))
    return r
