from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import FrozenSet

class ControlState(str, Enum):
    ENGINE_OFF="ENGINE_OFF"
    STARTING="STARTING"
    RUNNING="RUNNING"
    STOP_NEW_TRADES="STOP_NEW_TRADES"
    EMERGENCY_STOP="EMERGENCY_STOP"
    RECOVERY="RECOVERY"

class ControlAction(str, Enum):
    START="START"
    START_SUCCESS="START_SUCCESS"
    START_FAILURE="START_FAILURE"
    STOP_NEW_TRADES="STOP_NEW_TRADES"
    RESUME_NEW_TRADES="RESUME_NEW_TRADES"
    EMERGENCY_STOP="EMERGENCY_STOP"
    BEGIN_RECOVERY="BEGIN_RECOVERY"
    RECOVERY_COMPLETE="RECOVERY_COMPLETE"
    SHUTDOWN="SHUTDOWN"

class InvalidTransition(ValueError): pass

@dataclass(frozen=True)
class Transition:
    source: ControlState
    action: ControlAction
    target: ControlState

class ControlStateMachine:
    _TRANSITIONS: FrozenSet[Transition] = frozenset({
        Transition(ControlState.ENGINE_OFF, ControlAction.START, ControlState.STARTING),
        Transition(ControlState.STARTING, ControlAction.START_SUCCESS, ControlState.RUNNING),
        Transition(ControlState.STARTING, ControlAction.START_FAILURE, ControlState.ENGINE_OFF),
        Transition(ControlState.RUNNING, ControlAction.STOP_NEW_TRADES, ControlState.STOP_NEW_TRADES),
        Transition(ControlState.STOP_NEW_TRADES, ControlAction.RESUME_NEW_TRADES, ControlState.RUNNING),
        Transition(ControlState.RUNNING, ControlAction.EMERGENCY_STOP, ControlState.EMERGENCY_STOP),
        Transition(ControlState.STOP_NEW_TRADES, ControlAction.EMERGENCY_STOP, ControlState.EMERGENCY_STOP),
        Transition(ControlState.EMERGENCY_STOP, ControlAction.BEGIN_RECOVERY, ControlState.RECOVERY),
        Transition(ControlState.RECOVERY, ControlAction.RECOVERY_COMPLETE, ControlState.STOP_NEW_TRADES),
        Transition(ControlState.RUNNING, ControlAction.SHUTDOWN, ControlState.ENGINE_OFF),
        Transition(ControlState.STOP_NEW_TRADES, ControlAction.SHUTDOWN, ControlState.ENGINE_OFF),
        Transition(ControlState.RECOVERY, ControlAction.SHUTDOWN, ControlState.ENGINE_OFF),
        Transition(ControlState.STARTING, ControlAction.SHUTDOWN, ControlState.ENGINE_OFF),
    })
    def __init__(self, initial=ControlState.ENGINE_OFF):
        self._state=initial
    @property
    def state(self): return self._state
    def transition(self, action):
        for t in self._TRANSITIONS:
            if t.source is self._state and t.action is action:
                self._state=t.target
                return self._state
        raise InvalidTransition(f"invalid_transition:{self._state.value}:{action.value}")

@dataclass(frozen=True)
class TransitionPolicy:
    live_authorization_valid: bool=False
    recovery_clear: bool=False
    def authorize(self, state, action):
        if action is ControlAction.RESUME_NEW_TRADES:
            return state is ControlState.STOP_NEW_TRADES and self.live_authorization_valid and self.recovery_clear
        if action is ControlAction.RECOVERY_COMPLETE:
            return state is ControlState.RECOVERY and self.recovery_clear
        return True

class GuardedController:
    def __init__(self,machine): self.machine=machine
    def apply(self,action,policy=None):
        p=policy or TransitionPolicy()
        if not p.authorize(self.machine.state,action):
            raise InvalidTransition(f"policy_blocked:{self.machine.state.value}:{action.value}")
        return self.machine.transition(action)
