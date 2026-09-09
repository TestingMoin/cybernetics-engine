from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import os
from pathlib import Path


class ConfigValidationError(ValueError):
    """Raised when deployment/runtime configuration is unsafe or invalid."""


class TradingMode(str, Enum):
    PAPER = "paper"
    LIVE = "live"


@dataclass(frozen=True)
class DeploymentConfig:
    service_name: str = "cybernetics-engine"
    environment: str = "staging"
    trading_mode: TradingMode = TradingMode.PAPER
    data_dir: Path = Path("/opt/cybernetics-engine")
    secret_dir: Path = Path("/opt/cybernetics-engine/secrets")
    runtime_poll_seconds: float = 1.0
    order_submission_enabled: bool = False
    live_approval_id: str | None = None

    @property
    def live_authorization_configured(self) -> bool:
        return bool(self.trading_mode is TradingMode.LIVE and self.live_approval_id)

    @classmethod
    def from_env(cls, environ: dict[str, str] | None = None) -> "DeploymentConfig":
        env = os.environ if environ is None else environ

        mode_raw = env.get("CYBERNETICS_TRADING_MODE", "paper").strip().lower()
        try:
            mode = TradingMode(mode_raw)
        except ValueError as exc:
            raise ConfigValidationError("invalid_trading_mode") from exc

        environment = env.get("CYBERNETICS_ENV", "staging").strip().lower()
        if environment not in {"development", "test", "staging", "production"}:
            raise ConfigValidationError("invalid_environment")

        poll_raw = env.get("CYBERNETICS_RUNTIME_POLL_SECONDS", "1.0")
        try:
            poll = float(poll_raw)
        except ValueError as exc:
            raise ConfigValidationError("invalid_runtime_poll_seconds") from exc
        if poll <= 0:
            raise ConfigValidationError("runtime_poll_seconds_must_be_positive")

        order_enabled = _parse_bool(env.get("CYBERNETICS_ORDER_SUBMISSION_ENABLED", "false"))
        approval_id = env.get("CYBERNETICS_LIVE_APPROVAL_ID") or None

        # Safety invariant: config alone can never silently turn on live trading.
        if mode is TradingMode.LIVE and environment != "production":
            raise ConfigValidationError("live_mode_requires_production_environment")
        if mode is TradingMode.LIVE and not approval_id:
            if order_enabled:
                raise ConfigValidationError("order_submission_requires_approval_id")
            raise ConfigValidationError("live_mode_requires_approval_id")
        if order_enabled and mode is not TradingMode.LIVE:
            raise ConfigValidationError("order_submission_requires_live_mode")

        data_dir = Path(env.get("CYBERNETICS_DATA_DIR", "/opt/cybernetics-engine"))
        secret_dir = Path(env.get("CYBERNETICS_SECRET_DIR", str(data_dir / "secrets")))

        return cls(
            service_name=env.get("CYBERNETICS_SERVICE_NAME", "cybernetics-engine"),
            environment=environment,
            trading_mode=mode,
            data_dir=data_dir,
            secret_dir=secret_dir,
            runtime_poll_seconds=poll,
            order_submission_enabled=order_enabled,
            live_approval_id=approval_id,
        )

    def validate_filesystem(self) -> None:
        if not self.service_name.strip():
            raise ConfigValidationError("service_name_required")
        if self.data_dir.exists() and not self.data_dir.is_dir():
            raise ConfigValidationError("data_dir_not_directory")
        if self.secret_dir.exists() and not self.secret_dir.is_dir():
            raise ConfigValidationError("secret_dir_not_directory")


def _parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ConfigValidationError("invalid_boolean")
