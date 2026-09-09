from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable, Optional

@dataclass(frozen=True)
class MarketDataResponse:
    status_code: int
    payload: dict[str, Any]

class DhanMarketDataClient:
    """
    REST market-data facade.

    The supplied request callable is responsible for actual HTTP transport and
    authentication/rate limiting (Chunk 30). This class only validates request
    shapes and maps endpoints.
    """
    BASE_URL="https://api.dhan.co/v2"

    def __init__(self, request: Callable[..., Any],
                 dhan_client_id: Optional[str]=None):
        self._request=request
        self._client_id=dhan_client_id

    def _headers(self) -> dict[str,str]:
        headers={"Accept":"application/json","Content-Type":"application/json"}
        if self._client_id:
            headers["client-id"]=self._client_id
        return headers

    def ltp(self, instruments: list[dict[str,str]]):
        self._validate_instruments(instruments)
        return self._request(
            "POST", f"{self.BASE_URL}/marketfeed/ltp",
            json=self._group(instruments), headers=self._headers()
        )

    def ohlc(self, instruments: list[dict[str,str]]):
        self._validate_instruments(instruments)
        return self._request(
            "POST", f"{self.BASE_URL}/marketfeed/ohlc",
            json=self._group(instruments), headers=self._headers()
        )

    def quote(self, instruments: list[dict[str,str]]):
        self._validate_instruments(instruments)
        return self._request(
            "POST", f"{self.BASE_URL}/marketfeed/quote",
            json=self._group(instruments), headers=self._headers()
        )

    def historical(self, payload: dict[str,Any]):
        required={"securityId","exchangeSegment","instrument","fromDate","toDate"}
        missing=required-payload.keys()
        if missing:
            raise ValueError(f"historical_missing:{','.join(sorted(missing))}")
        return self._request(
            "POST", f"{self.BASE_URL}/charts/historical",
            json=dict(payload), headers=self._headers()
        )

    def intraday(self, payload: dict[str,Any]):
        required={"securityId","exchangeSegment","instrument","interval","fromDate","toDate"}
        missing=required-payload.keys()
        if missing:
            raise ValueError(f"intraday_missing:{','.join(sorted(missing))}")
        interval=str(payload["interval"])
        if interval not in {"1","5","15","25","60"}:
            raise ValueError("intraday_interval_unsupported")
        return self._request(
            "POST", f"{self.BASE_URL}/charts/intraday",
            json=dict(payload), headers=self._headers()
        )

    @staticmethod
    def _validate_instruments(instruments):
        if not instruments:
            raise ValueError("instruments_required")
        if len(instruments)>1000:
            raise ValueError("market_quote_instrument_limit_exceeded")
        for item in instruments:
            if not item.get("ExchangeSegment") or not item.get("SecurityId"):
                raise ValueError("instrument_requires_exchange_segment_and_security_id")

    @staticmethod
    def _group(instruments):
        grouped={}
        for item in instruments:
            grouped.setdefault(item["ExchangeSegment"],[]).append(item["SecurityId"])
        return grouped
