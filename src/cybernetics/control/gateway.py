from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
import time
from typing import Callable, Protocol

from cybernetics.runtime.control import (
    ControlAction, ControlState, GuardedController, InvalidTransition,
    TransitionPolicy,
)

class CommandName(str, Enum):
    ENGINE_START="ENGINE_START"
    ENGINE_START_SUCCESS="ENGINE_START_SUCCESS"
    ENGINE_START_FAILURE="ENGINE_START_FAILURE"
    STOP_NEW_TRADES="STOP_NEW_TRADES"
    RESUME_NEW_TRADES="RESUME_NEW_TRADES"
    EMERGENCY_STOP="EMERGENCY_STOP"
    BEGIN_RECOVERY="BEGIN_RECOVERY"
    RECOVERY_COMPLETE="RECOVERY_COMPLETE"
    ENGINE_SHUTDOWN="ENGINE_SHUTDOWN"

_MAP = {
    CommandName.ENGINE_START: ControlAction.START,
    CommandName.ENGINE_START_SUCCESS: ControlAction.START_SUCCESS,
    CommandName.ENGINE_START_FAILURE: ControlAction.START_FAILURE,
    CommandName.STOP_NEW_TRADES: ControlAction.STOP_NEW_TRADES,
    CommandName.RESUME_NEW_TRADES: ControlAction.RESUME_NEW_TRADES,
    CommandName.EMERGENCY_STOP: ControlAction.EMERGENCY_STOP,
    CommandName.BEGIN_RECOVERY: ControlAction.BEGIN_RECOVERY,
    CommandName.RECOVERY_COMPLETE: ControlAction.RECOVERY_COMPLETE,
    CommandName.ENGINE_SHUTDOWN: ControlAction.SHUTDOWN,
}

class CommandResult(str, Enum):
    ACCEPTED="ACCEPTED"
    DUPLICATE="DUPLICATE"
    REJECTED="REJECTED"
    STALE="STALE"

@dataclass(frozen=True)
class ControlCommand:
    command_id: str
    command: CommandName
    issued_at: float
    source: str
    expected_state: ControlState|None=None

@dataclass(frozen=True)
class CommandReceipt:
    command_id: str
    result: CommandResult
    state: ControlState
    reason: str

class CommandIdStore(Protocol):
    def seen(self, command_id: str)->bool: ...
    def remember(self, command_id: str)->None: ...

class AuditSink(Protocol):
    def record(self, **event)->None: ...

@dataclass(frozen=True)
class GatewayPolicy:
    max_command_age_seconds: float=30.0
    allowed_sources: frozenset[str]=frozenset({"PWA","TELEGRAM","SYSTEM"})
    require_expected_state_for_external_resume: bool=True

class ControlCommandGateway:
    def __init__(self, controller, id_store, audit, *, policy=None, clock=time.time):
        self.controller=controller
        self.id_store=id_store
        self.audit=audit
        self.policy=policy or GatewayPolicy()
        self.clock=clock

    def _audit(self, cmd, result, reason):
        self.audit.record(
            command_id=cmd.command_id, command=cmd.command.value,
            source=cmd.source, result=result.value,
            state=self.controller.machine.state.value,
            reason=reason, issued_at=cmd.issued_at
        )

    def _receipt(self, cmd, result, reason):
        self._audit(cmd,result,reason)
        return CommandReceipt(cmd.command_id,result,self.controller.machine.state,reason)

    def handle(self, cmd, *, policy=None):
        if not cmd.command_id:
            return self._receipt(cmd,CommandResult.REJECTED,"command_id_required")
        if cmd.source not in self.policy.allowed_sources:
            return self._receipt(cmd,CommandResult.REJECTED,"source_not_allowed")
        age=self.clock()-cmd.issued_at
        if age<0:
            return self._receipt(cmd,CommandResult.REJECTED,"command_from_future")
        if age>self.policy.max_command_age_seconds:
            return self._receipt(cmd,CommandResult.STALE,"command_expired")
        if self.id_store.seen(cmd.command_id):
            return self._receipt(cmd,CommandResult.DUPLICATE,"command_already_seen")
        if (cmd.command is CommandName.RESUME_NEW_TRADES
            and cmd.source in {"PWA","TELEGRAM"}
            and self.policy.require_expected_state_for_external_resume
            and cmd.expected_state is None):
            return self._receipt(cmd,CommandResult.REJECTED,"expected_state_required_for_resume")
        if cmd.expected_state is not None and cmd.expected_state is not self.controller.machine.state:
            return self._receipt(cmd,CommandResult.REJECTED,"expected_state_mismatch")
        try:
            state=self.controller.apply(_MAP[cmd.command], policy)
        except InvalidTransition as exc:
            return self._receipt(cmd,CommandResult.REJECTED,str(exc))
        self.id_store.remember(cmd.command_id)
        return self._receipt(cmd,CommandResult.ACCEPTED,"command_applied")
