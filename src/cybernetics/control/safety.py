from dataclasses import dataclass
from enum import Enum
from threading import RLock

class ControlState(str, Enum):
    RUNNING="RUNNING"
    STOP_NEW_TRADES="STOP_NEW_TRADES"
    EMERGENCY_STOP="EMERGENCY_STOP"

@dataclass(frozen=True)
class SafetySnapshot:
    state: ControlState
    live_authorized: bool
    reason: str
    version: int

class SafetyController:
    """Thread-safe local safety state. It never talks to a broker."""
    def __init__(self):
        self._lock=RLock()
        self._state=ControlState.STOP_NEW_TRADES
        self._live_authorized=False
        self._reason="startup_default_safe"
        self._version=0

    def snapshot(self):
        with self._lock:
            return SafetySnapshot(self._state,self._live_authorized,self._reason,self._version)

    def enable_engine(self):
        with self._lock:
            if self._state==ControlState.EMERGENCY_STOP:
                raise RuntimeError("emergency stop active; explicit recovery required")
            self._state=ControlState.RUNNING
            self._reason="operator_enabled_engine"
            self._version+=1

    def stop_new_trades(self, reason="operator_stop"):
        with self._lock:
            self._state=ControlState.STOP_NEW_TRADES
            self._reason=reason
            self._version+=1

    def emergency_stop(self, reason="emergency_stop"):
        with self._lock:
            self._state=ControlState.EMERGENCY_STOP
            self._live_authorized=False
            self._reason=reason
            self._version+=1

    def authorize_live(self):
        with self._lock:
            if self._state != ControlState.RUNNING:
                raise RuntimeError("engine must be running before live authorization")
            self._live_authorized=True
            self._reason="operator_live_authorized"
            self._version+=1

    def deauthorize_live(self):
        with self._lock:
            self._live_authorized=False
            self._reason="operator_live_deauthorized"
            self._version+=1

    def recover(self, reason="operator_recovery"):
        with self._lock:
            self._state=ControlState.STOP_NEW_TRADES
            self._live_authorized=False
            self._reason=reason
            self._version+=1

    def can_open_new_trade(self):
        with self._lock:
            return self._state==ControlState.RUNNING and self._live_authorized
