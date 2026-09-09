from __future__ import annotations
from math import sqrt
from typing import Iterable

def _xs(values):
    x=list(values)
    if not x: raise ValueError("values_required")
    return x

def sma(values,period:int):
    x=_xs(values)
    if period<=0: raise ValueError("invalid_period")
    return None if len(x)<period else sum(x[-period:])/period

def ema(values,period:int):
    x=_xs(values)
    if period<=0: raise ValueError("invalid_period")
    if len(x)<period:return None
    value=sum(x[:period])/period
    alpha=2/(period+1)
    for v in x[period:]:
        value=alpha*v+(1-alpha)*value
    return value

def wma(values,period:int):
    x=_xs(values)
    if period<=0: raise ValueError("invalid_period")
    if len(x)<period:return None
    tail=x[-period:]; denom=period*(period+1)/2
    return sum((i+1)*v for i,v in enumerate(tail))/denom

def rsi(values,period:int=14):
    x=_xs(values)
    if period<=0: raise ValueError("invalid_period")
    if len(x)<=period:return None
    gains=[];losses=[]
    for a,b in zip(x[-period-1:-1],x[-period:]):
        d=b-a;gains.append(max(d,0));losses.append(max(-d,0))
    ag=sum(gains)/period;al=sum(losses)/period
    if al==0:return 100.0 if ag>0 else 50.0
    rs=ag/al
    return 100-100/(1+rs)

def true_ranges(high,low,close):
    h=_xs(high);l=_xs(low);c=_xs(close)
    if not(len(h)==len(l)==len(c)):raise ValueError("ohlc_length_mismatch")
    out=[];prev=None
    for hi,lo,cl in zip(h,l,c):
        out.append(hi-lo if prev is None else max(hi-lo,abs(hi-prev),abs(lo-prev)))
        prev=cl
    return out

def atr(high,low,close,period:int=14):
    trs=true_ranges(high,low,close)
    return None if len(trs)<period else sum(trs[-period:])/period

def bollinger_bands(values,period:int=20,mult:float=2.0):
    x=_xs(values)
    if period<=0 or mult<0:raise ValueError("invalid_bollinger_parameters")
    if len(x)<period:return None
    tail=x[-period:];mid=sum(tail)/period
    sd=sqrt(sum((v-mid)**2 for v in tail)/period)
    return {"mid":mid,"upper":mid+mult*sd,"lower":mid-mult*sd}

def roc(values,period:int=12):
    x=_xs(values)
    if period<=0:raise ValueError("invalid_period")
    if len(x)<=period:return None
    base=x[-period-1]
    return None if base==0 else (x[-1]/base-1)*100

def highest(values,period:int):
    x=_xs(values)
    if period<=0:raise ValueError("invalid_period")
    return None if len(x)<period else max(x[-period:])

def lowest(values,period:int):
    x=_xs(values)
    if period<=0:raise ValueError("invalid_period")
    return None if len(x)<period else min(x[-period:])

def stochastic_k(high,low,close,period:int=14):
    h=_xs(high);l=_xs(low);c=_xs(close)
    if not(len(h)==len(l)==len(c)):raise ValueError("ohlc_length_mismatch")
    if len(c)<period:return None
    hi=max(h[-period:]);lo=min(l[-period:])
    return 50.0 if hi==lo else (c[-1]-lo)/(hi-lo)*100

def stochastic_d(high,low,close,period:int=14,smooth:int=3):
    h=_xs(high);l=_xs(low);c=_xs(close)
    if not(len(h)==len(l)==len(c)):raise ValueError("ohlc_length_mismatch")
    if smooth<=0 or len(c)<period+smooth-1:return None
    ks=[]
    for i in range(len(c)-smooth+1,len(c)):
        hi=max(h[i-period+1:i+1]);lo=min(l[i-period+1:i+1])
        ks.append(50.0 if hi==lo else (c[i]-lo)/(hi-lo)*100)
    return sum(ks)/smooth

def macd(values,fast:int=12,slow:int=26,signal:int=9):
    x=_xs(values)
    if not(0<fast<slow and signal>0):raise ValueError("invalid_macd_parameters")
    if len(x)<slow+signal-1:return None
    fast_s=[];slow_s=[]
    for i in range(slow-1,len(x)):
        fast_s.append(ema(x[:i+1],fast));slow_s.append(ema(x[:i+1],slow))
    line=[a-b for a,b in zip(fast_s,slow_s)]
    sig=ema(line,signal)
    if sig is None:return None
    return {"macd":line[-1],"signal":sig,"histogram":line[-1]-sig}

def adx(high,low,close,period:int=14):
    h=_xs(high);l=_xs(low);c=_xs(close)
    if not(len(h)==len(l)==len(c)):raise ValueError("ohlc_length_mismatch")
    if len(c)<period+1:return None
    plus=[];minus=[];trs=[]
    for i in range(1,len(c)):
        up=h[i]-h[i-1];down=l[i-1]-l[i]
        plus.append(up if up>down and up>0 else 0)
        minus.append(down if down>up and down>0 else 0)
        trs.append(max(h[i]-l[i],abs(h[i]-c[i-1]),abs(l[i]-c[i-1])))
    tr=sum(trs[-period:])/period
    if tr==0:return 0.0
    p=sum(plus[-period:])/period/tr*100;m=sum(minus[-period:])/period/tr*100
    return 0.0 if p+m==0 else abs(p-m)/(p+m)*100

def obv(close,volume):
    c=_xs(close);v=_xs(volume)
    if len(c)!=len(v):raise ValueError("price_volume_length_mismatch")
    value=0.0
    for a,b,vol in zip(c,c[1:],v[1:]):
        if b>a:value+=vol
        elif b<a:value-=vol
    return value

def vwap(high,low,close,volume):
    h=_xs(high);l=_xs(low);c=_xs(close);v=_xs(volume)
    if not(len(h)==len(l)==len(c)==len(v)):raise ValueError("ohlcv_length_mismatch")
    den=sum(v)
    if den==0:return None
    return sum(((hi+lo+cl)/3)*vol for hi,lo,cl,vol in zip(h,l,c,v))/den
