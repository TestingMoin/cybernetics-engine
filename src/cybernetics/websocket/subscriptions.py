from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Iterable

class SubscriptionMode(str, Enum):
    TICKER="TICKER"
    QUOTE="QUOTE"
    FULL="FULL"

_REQUEST_CODES={
    SubscriptionMode.TICKER:15,
    SubscriptionMode.QUOTE:17,
    SubscriptionMode.FULL:21,
}
_UNSUB_CODES={
    SubscriptionMode.TICKER:16,
    SubscriptionMode.QUOTE:18,
    SubscriptionMode.FULL:22,
}

@dataclass(frozen=True, order=True)
class Instrument:
    exchange_segment: str
    security_id: str

class SubscriptionManager:
    """
    Owns desired subscription state and creates Dhan V2 JSON messages.

    Dhan accepts at most 100 instruments in one JSON subscription message and
    up to 5000 instruments per WebSocket connection. The manager chunks messages
    at 100 and validates the connection-level ceiling at 5000.
    """
    MAX_PER_MESSAGE=100
    MAX_PER_CONNECTION=5000

    def __init__(self):
        self._desired: dict[SubscriptionMode,set[Instrument]]={
            mode:set() for mode in SubscriptionMode
        }

    def set_desired(self, mode:SubscriptionMode,
                    instruments:Iterable[Instrument]) -> None:
        unique=set(instruments)
        if len(unique)>self.MAX_PER_CONNECTION:
            raise ValueError("connection_instrument_limit_exceeded")
        self._desired[mode]=unique

    def add(self, mode:SubscriptionMode, instruments:Iterable[Instrument]) -> None:
        new=self._desired[mode] | set(instruments)
        if len(new)>self.MAX_PER_CONNECTION:
            raise ValueError("connection_instrument_limit_exceeded")
        self._desired[mode]=new

    def remove(self, mode:SubscriptionMode, instruments:Iterable[Instrument]) -> None:
        self._desired[mode]-=set(instruments)

    def desired(self, mode:SubscriptionMode)->set[Instrument]:
        return set(self._desired[mode])

    def messages(self, mode:SubscriptionMode, subscribe:bool=True)->list[dict]:
        items=sorted(self._desired[mode])
        code=_REQUEST_CODES[mode] if subscribe else _UNSUB_CODES[mode]
        return [
            {
                "RequestCode":code,
                "InstrumentCount":len(chunk),
                "InstrumentList":[
                    {"ExchangeSegment":i.exchange_segment,"SecurityId":i.security_id}
                    for i in chunk
                ],
            }
            for chunk in _chunks(items,self.MAX_PER_MESSAGE)
        ]

def _chunks(items:list, size:int):
    for i in range(0,len(items),size):
        yield items[i:i+size]
