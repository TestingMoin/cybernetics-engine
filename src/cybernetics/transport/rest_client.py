from __future__ import annotations
from dataclasses import dataclass
import random
import time
from typing import Any, Callable, Optional

@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    base_delay: float = 0.25
    max_delay: float = 5.0
    jitter: float = 0.10

@dataclass(frozen=True)
class RestResponse:
    status_code: int
    payload: Any
    headers: dict[str,str]

class DhanRestClient:
    """
    Transport-only client. Authentication headers are supplied by an injected
    token provider; retry policy never retries non-idempotent order submission
    unless the caller explicitly opts in.

    Retry defaults target transport errors and rate/server responses.
    """
    RETRYABLE_STATUS={429,500,502,503,504}

    def __init__(self, transport: Callable[..., RestResponse],
                 token_provider: Callable[[], dict[str,str]],
                 governor,
                 retry_policy: RetryPolicy = RetryPolicy(),
                 sleeper=time.sleep,
                 rng=random.random):
        if retry_policy.max_attempts < 1:
            raise ValueError("max_attempts_must_be_positive")
        self._transport=transport
        self._token_provider=token_provider
        self._governor=governor
        self._policy=retry_policy
        self._sleep=sleeper
        self._rng=rng

    def request(self, method: str, url: str, *,
                json: Any=None, params: Any=None,
                retry_safe: bool=False) -> RestResponse:
        method=method.upper()
        attempts=self._policy.max_attempts if retry_safe else 1

        last_exc=None
        for attempt in range(1,attempts+1):
            self._governor.acquire()
            try:
                headers={"Accept":"application/json", **self._token_provider()}
                if json is not None:
                    headers["Content-Type"]="application/json"
                response=self._transport(method,url,headers=headers,json=json,params=params)
                if retry_safe and response.status_code in self.RETRYABLE_STATUS and attempt < attempts:
                    self._backoff(attempt)
                    continue
                return response
            except (TimeoutError, ConnectionError, OSError) as exc:
                last_exc=exc
                if attempt >= attempts:
                    raise
                if not retry_safe:
                    raise
                self._backoff(attempt)
        raise last_exc or RuntimeError("request_failed")

    def _backoff(self, attempt: int):
        raw=min(self._policy.max_delay,
                self._policy.base_delay*(2**(attempt-1)))
        self._sleep(raw + self._rng()*self._policy.jitter)
