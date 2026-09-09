from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import ssl
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from cybernetics.auth.secret_provider import FileSecretProvider
from cybernetics.brokers.interface import BrokerAdapter, BrokerOrderRequest, BrokerOrderResult


class DhanTransportError(RuntimeError):
    """Raised for Dhan HTTP/transport failures."""


@dataclass(frozen=True)
class DhanReadOnlyConfig:
    client_id: str
    access_token: str
    timeout_seconds: float = 10.0

    @classmethod
    def from_secret_dir(cls, directory: str | Path, timeout_seconds: float = 10.0) -> "DhanReadOnlyConfig":
        provider = FileSecretProvider(directory)
        client_id = provider.get("dhan_client_id")
        access_token = provider.get("dhan_access_token")
        if timeout_seconds <= 0:
            raise ValueError("dhan_timeout_must_be_positive")
        return cls(client_id=client_id, access_token=access_token, timeout_seconds=timeout_seconds)


class DhanStdlibTransport:
    """Small stdlib-only HTTPS transport for read-only Dhan V2 calls."""

    def __init__(self, timeout_seconds: float = 10.0, opener: Callable[..., Any] | None = None):
        if timeout_seconds <= 0:
            raise ValueError("timeout_must_be_positive")
        self.timeout_seconds = timeout_seconds
        self._opener = opener or urlopen
        self.base_url = "https://api.dhan.co/v2"

    def __call__(self, method: str, path: str, *, access_token: str, client_id: str | None = None,
                 json_body: Any = None, params: dict[str, str] | None = None) -> Any:
        url = f"{self.base_url}{path}"
        if params:
            url = f"{url}?{urlencode(params)}"
        headers = {"Accept": "application/json", "access-token": access_token}
        if client_id:
            headers["client-id"] = client_id
        data = None
        if json_body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(json_body).encode("utf-8")
        request = Request(url, data=data, headers=headers, method=method.upper())
        try:
            with self._opener(request, timeout=self.timeout_seconds, context=ssl.create_default_context()) as response:
                raw = response.read().decode("utf-8")
                if not raw:
                    return {}
                return json.loads(raw)
        except HTTPError as exc:
            try:
                body = exc.read().decode("utf-8")
                payload = json.loads(body) if body else {}
            except Exception:
                payload = {}
            raise DhanTransportError(f"http_{exc.code}:{payload.get('errorMessage') or payload.get('message') or 'dhan_request_failed'}") from exc
        except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            raise DhanTransportError(f"dhan_transport_failed:{type(exc).__name__}") from exc


@dataclass
class DhanReadOnlyBrokerAdapter(BrokerAdapter):
    """Read-only Dhan broker adapter used for staging health/reconciliation input.

    Order placement and cancellation remain hard blocked in this chunk.
    """

    config: DhanReadOnlyConfig
    transport: DhanStdlibTransport
    health_cache_seconds: float = 30.0

    name: str = "DHAN_V2"

    def __post_init__(self) -> None:
        if self.health_cache_seconds <= 0:
            raise ValueError("health_cache_seconds_must_be_positive")
        self._health_cache_until = 0.0
        self._health_report: dict[str, Any] | None = None
        self._clock = __import__("time").monotonic

    def _profile(self) -> dict[str, Any]:
        payload = self.transport("GET", "/profile", access_token=self.config.access_token)
        return payload if isinstance(payload, dict) else {}

    def health(self) -> dict[str, Any]:
        now = self._clock()
        if self._health_report is not None and now < self._health_cache_until:
            return dict(self._health_report)
        try:
            profile = self._profile()
            valid = bool(profile.get("dhanClientId") or profile.get("tokenValidity"))
            self._health_report = {
                "broker": self.name,
                "configured": True,
                "authenticated": valid,
                "valid": valid,
                "read_only": True,
                "profile_client_id": str(profile.get("dhanClientId")) if profile.get("dhanClientId") else None,
                "token_validity": str(profile.get("tokenValidity")) if profile.get("tokenValidity") else None,
            }
        except Exception as exc:
            self._health_report = {
                "broker": self.name,
                "configured": True,
                "authenticated": False,
                "valid": False,
                "read_only": True,
                "error": type(exc).__name__,
            }
        self._health_cache_until = now + self.health_cache_seconds
        return dict(self._health_report)

    def get_positions(self) -> list[dict[str, Any]]:
        payload = self.transport("GET", "/positions", access_token=self.config.access_token)
        return payload if isinstance(payload, list) else []

    def get_orders(self) -> list[dict[str, Any]]:
        payload = self.transport("GET", "/orders", access_token=self.config.access_token)
        return payload if isinstance(payload, list) else []

    def place_order(self, request: BrokerOrderRequest) -> BrokerOrderResult:
        return BrokerOrderResult(self.name, False, None, "BLOCKED", "read_only_staging_adapter")

    def cancel_order(self, broker_order_id: str) -> BrokerOrderResult:
        return BrokerOrderResult(self.name, False, broker_order_id, "BLOCKED", "read_only_staging_adapter")


def build_dhan_read_only_broker(secret_dir: str | Path, *, timeout_seconds: float = 10.0,
                                health_cache_seconds: float = 30.0) -> DhanReadOnlyBrokerAdapter | None:
    provider = FileSecretProvider(secret_dir)
    client_id = provider.get("dhan_client_id", required=False)
    access_token = provider.get("dhan_access_token", required=False)
    if not client_id or not access_token:
        return None
    config = DhanReadOnlyConfig(client_id=client_id, access_token=access_token, timeout_seconds=timeout_seconds)
    return DhanReadOnlyBrokerAdapter(
        config=config,
        transport=DhanStdlibTransport(timeout_seconds=timeout_seconds),
        health_cache_seconds=health_cache_seconds,
    )
