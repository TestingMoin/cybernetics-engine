from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Iterable, Protocol


class FlattenDecision(str, Enum):
    READY = "READY"
    BLOCKED = "BLOCKED"


class ExitOrderState(str, Enum):
    PLANNED = "PLANNED"
    SUBMITTED = "SUBMITTED"
    UNKNOWN = "UNKNOWN"
    COMPLETED = "COMPLETED"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class OpenPosition:
    position_id: str
    security_id: str
    side: str
    quantity: int


@dataclass(frozen=True)
class FlattenIntent:
    intent_id: str
    position_id: str
    security_id: str
    exit_side: str
    quantity: int
    emergency_id: str


@dataclass(frozen=True)
class FlattenResult:
    decision: FlattenDecision
    reason: str
    intents: tuple[FlattenIntent, ...] = ()


class EmergencyFlattenState(Protocol):
    def was_requested(self, emergency_id: str) -> bool: ...
    def remember_request(self, emergency_id: str, request_id: str) -> None: ...
    def was_position_exit_planned(self, emergency_id: str, position_id: str) -> bool: ...
    def remember_position_exit(self, emergency_id: str, position_id: str, intent_id: str) -> None: ...


class EmergencyFlattenCoordinator:
    """
    Emergency flatten planner.

    This layer ONLY plans one exit intent per position. It does not call the
    broker, does not reuse the normal ENTRY execution gate, and does not
    infer/reprice quantities.

    A downstream broker-exit adapter must remain separately idempotent.
    """

    def __init__(self, state: EmergencyFlattenState):
        self.state = state

    def plan(
        self,
        *,
        emergency_id: str,
        request_id: str,
        positions: Iterable[OpenPosition],
        emergency_active: bool,
        broker_available: bool,
    ) -> FlattenResult:
        if not emergency_active:
            return FlattenResult(
                FlattenDecision.BLOCKED, "emergency_not_active"
            )
        if not emergency_id:
            return FlattenResult(
                FlattenDecision.BLOCKED, "emergency_id_required"
            )
        if not request_id:
            return FlattenResult(
                FlattenDecision.BLOCKED, "request_id_required"
            )
        if not broker_available:
            return FlattenResult(
                FlattenDecision.BLOCKED, "broker_unavailable"
            )

        if self.state.was_requested(emergency_id):
            # A repeated emergency request returns no new intents.
            return FlattenResult(
                FlattenDecision.READY, "emergency_flatten_already_requested"
            )

        intents: list[FlattenIntent] = []
        for position in positions:
            if position.quantity <= 0:
                continue
            if not position.position_id or not position.security_id:
                return FlattenResult(
                    FlattenDecision.BLOCKED, "position_identity_invalid"
                )
            if position.side not in {"BUY", "SELL"}:
                return FlattenResult(
                    FlattenDecision.BLOCKED, "position_side_invalid"
                )
            if self.state.was_position_exit_planned(
                emergency_id, position.position_id
            ):
                continue

            exit_side = "SELL" if position.side == "BUY" else "BUY"
            intent_id = f"EMERGENCY:{emergency_id}:{position.position_id}"
            intents.append(
                FlattenIntent(
                    intent_id=intent_id,
                    position_id=position.position_id,
                    security_id=position.security_id,
                    exit_side=exit_side,
                    quantity=position.quantity,
                    emergency_id=emergency_id,
                )
            )

        self.state.remember_request(emergency_id, request_id)
        for intent in intents:
            self.state.remember_position_exit(
                emergency_id, intent.position_id, intent.intent_id
            )

        return FlattenResult(
            FlattenDecision.READY,
            "emergency_flatten_plan_created",
            tuple(intents),
        )


class EmergencyExitExecutor:
    """
    Separate exit-only execution boundary.

    `submit_exit` is injected. The executor never routes an emergency exit
    through an entry/new-trade gate.
    """

    def execute(
        self,
        intents: Iterable[FlattenIntent],
        *,
        submit_exit: Callable[[FlattenIntent], ExitOrderState],
    ) -> tuple[tuple[FlattenIntent, ExitOrderState], ...]:
        results=[]
        for intent in intents:
            state=submit_exit(intent)
            if state not in {
                ExitOrderState.SUBMITTED,
                ExitOrderState.UNKNOWN,
                ExitOrderState.COMPLETED,
            }:
                results.append((intent, ExitOrderState.BLOCKED))
                continue
            results.append((intent,state))
        return tuple(results)
