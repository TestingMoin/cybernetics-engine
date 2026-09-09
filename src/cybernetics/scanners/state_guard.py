from .models import ScannerState
class D:
 def __init__(self,a,r): self.allowed=a;self.reason=r
def can_process_market_event(runtime):
 return D(True,"scanner_running") if runtime.state==ScannerState.RUNNING else D(False,f"scanner_state:{runtime.state.value}")
