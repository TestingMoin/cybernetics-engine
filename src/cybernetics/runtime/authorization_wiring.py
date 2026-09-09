from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from cybernetics.auth.token_manager import TokenState
from cybernetics.config.settings import DeploymentConfig, TradingMode
from .authorization import LiveAuthorization


class TokenStateProbe(Protocol):
    def state(self) -> TokenState: ...


@dataclass(frozen=True)
class LiveAuthorizationSnapshot:
    config_eligible: bool
    token_valid: bool
    approval_valid: bool
    authorized: bool
    reason: str | None = None


class LiveAuthorizationRuntimeWiring:
    """Read-only bridge from deployment approval + Dhan token state to runtime auth.

    LIVE authorization is intentionally independent of engine/control state and
    emergency state. Only an explicit production LIVE configuration, a valid
    approval id, and a currently VALID Dhan access token can authorize new trades.
    RENEW_REQUIRED is treated as unsafe for new entries so the runtime can renew
    before trading resumes.
    """

    def __init__(
        self,
        config: DeploymentConfig,
        token_manager: TokenStateProbe,
        authorization: LiveAuthorization,
    ) -> None:
        self._config = config
        self._token_manager = token_manager
        self._authorization = authorization

    def snapshot(self) -> LiveAuthorizationSnapshot:
        config_eligible = self._config.trading_mode is TradingMode.LIVE
        approval_valid = bool(self._config.live_approval_id) and self._authorization.valid
        token_valid = False
        reason: str | None = None
        try:
            token_valid = self._token_manager.state() is TokenState.VALID
        except Exception:
            reason = "token_state_probe_failed"

        if not config_eligible:
            reason = reason or "live_mode_not_enabled"
        elif not self._config.live_approval_id:
            reason = reason or "approval_id_missing"
        elif not self._authorization.valid:
            reason = reason or "runtime_authorization_not_approved"
        elif not token_valid:
            reason = reason or "dhan_token_not_valid"

        return LiveAuthorizationSnapshot(
            config_eligible=config_eligible,
            token_valid=token_valid,
            approval_valid=approval_valid,
            authorized=config_eligible and approval_valid and token_valid,
            reason=reason,
        )

    def live_authorization_valid(self) -> bool:
        return self.snapshot().authorized
