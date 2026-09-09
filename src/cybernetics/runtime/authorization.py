from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LiveAuthorization:
    """
    Independent live-trading authorization state.

    This object is deliberately detached from engine/control-state transitions.
    """
    valid: bool = False
    approval_id: str | None = None

    def revoke(self) -> "LiveAuthorization":
        return LiveAuthorization(valid=False, approval_id=None)

    def approve(self, approval_id: str) -> "LiveAuthorization":
        if not approval_id:
            raise ValueError("approval_id_required")
        return LiveAuthorization(valid=True, approval_id=approval_id)
