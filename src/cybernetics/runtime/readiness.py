"""Backward-compatible facade for the canonical runtime readiness model.

The authoritative implementation lives in ``cybernetics.runtime.state``.
"""

from .state import (
    ControlState,
    EmergencyState,
    EngineMode,
    RuntimeInputs,
    RuntimeReadiness,
    evaluate_runtime,
)

__all__ = [
    "ControlState",
    "EmergencyState",
    "EngineMode",
    "RuntimeInputs",
    "RuntimeReadiness",
    "evaluate_runtime",
]
