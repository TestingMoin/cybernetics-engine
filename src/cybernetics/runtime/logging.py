from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import os
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Iterable


_SENSITIVE_KEYS = {
    "access_token", "api_key", "api_secret", "secret", "password", "pin",
    "totp", "otp", "authorization", "auth_token", "refresh_token",
}


def _redact(value: object, *, key: str | None = None) -> object:
    if key and key.lower() in _SENSITIVE_KEYS:
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(k): _redact(v, key=str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_redact(v) for v in value]
    return value


class JsonFormatter(logging.Formatter):
    """Structured JSON formatter with credential redaction."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        extras = getattr(record, "audit", None)
        if extras is not None:
            payload["audit"] = _redact(extras)
        return json.dumps(payload, sort_keys=True, ensure_ascii=False)


@dataclass(frozen=True)
class RuntimeLoggingConfig:
    level: str = "INFO"
    log_file: str | None = None
    max_bytes: int = 10 * 1024 * 1024
    backup_count: int = 5

    def __post_init__(self) -> None:
        if self.max_bytes <= 0:
            raise ValueError("max_bytes_must_be_positive")
        if self.backup_count < 0:
            raise ValueError("backup_count_must_not_be_negative")


def configure_runtime_logging(
    config: RuntimeLoggingConfig | None = None,
    *,
    logger_name: str = "cybernetics",
    handlers: Iterable[logging.Handler] | None = None,
) -> logging.Logger:
    """Configure deterministic JSON logging; repeated calls replace owned handlers."""
    cfg = config or RuntimeLoggingConfig(
        level=os.getenv("CYBERNETICS_LOG_LEVEL", "INFO").upper(),
        log_file=os.getenv("CYBERNETICS_LOG_FILE"),
    )
    logger = logging.getLogger(logger_name)
    logger.setLevel(getattr(logging, cfg.level.upper(), logging.INFO))
    logger.propagate = False

    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    formatter = JsonFormatter()
    chosen = list(handlers) if handlers is not None else []
    if not chosen:
        stream = logging.StreamHandler()
        stream.setFormatter(formatter)
        chosen.append(stream)
        if cfg.log_file:
            path = Path(cfg.log_file).expanduser()
            path.parent.mkdir(parents=True, exist_ok=True)
            file_handler = RotatingFileHandler(
                path,
                maxBytes=cfg.max_bytes,
                backupCount=cfg.backup_count,
                encoding="utf-8",
            )
            file_handler.setFormatter(formatter)
            chosen.append(file_handler)

    for handler in chosen:
        if handler.formatter is None:
            handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger


def runtime_logger(name: str = "cybernetics.runtime") -> logging.Logger:
    return logging.getLogger(name)


__all__ = ["JsonFormatter", "RuntimeLoggingConfig", "configure_runtime_logging", "runtime_logger"]
