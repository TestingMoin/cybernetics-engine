from .rate_limiter import LimitWindow, RateLimitGovernor

# Dhan V2 published budgets.
# Order APIs: 10/sec, 250/min, 1000/hour, 7000/day.
# Data APIs: 5/sec, 100000/day.
# Quote APIs: 1/sec.
# Non-trading APIs: 20/sec.
ORDER_LIMITS=[
    LimitWindow(10,1),
    LimitWindow(250,60),
    LimitWindow(1000,3600),
    LimitWindow(7000,86400),
]
DATA_LIMITS=[
    LimitWindow(5,1),
    LimitWindow(100000,86400),
]
QUOTE_LIMITS=[LimitWindow(1,1)]
NON_TRADING_LIMITS=[LimitWindow(20,1)]

def order_governor(clock=None,sleeper=None):
    kwargs={}
    if clock is not None: kwargs["clock"]=clock
    if sleeper is not None: kwargs["sleeper"]=sleeper
    return RateLimitGovernor(ORDER_LIMITS,**kwargs)

def data_governor(clock=None,sleeper=None):
    kwargs={}
    if clock is not None: kwargs["clock"]=clock
    if sleeper is not None: kwargs["sleeper"]=sleeper
    return RateLimitGovernor(DATA_LIMITS,**kwargs)

def quote_governor(clock=None,sleeper=None):
    kwargs={}
    if clock is not None: kwargs["clock"]=clock
    if sleeper is not None: kwargs["sleeper"]=sleeper
    return RateLimitGovernor(QUOTE_LIMITS,**kwargs)

def non_trading_governor(clock=None,sleeper=None):
    kwargs={}
    if clock is not None: kwargs["clock"]=clock
    if sleeper is not None: kwargs["sleeper"]=sleeper
    return RateLimitGovernor(NON_TRADING_LIMITS,**kwargs)
