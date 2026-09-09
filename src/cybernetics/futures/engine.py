from __future__ import annotations
from dataclasses import asdict
from decimal import Decimal
from typing import Optional

from .models import ContractSpec, FuturesQuote, FuturesState


class FuturesEngine:
    """Pure analytics/state engine. Never submits broker orders."""

    def __init__(self) -> None:
        self._states: dict[str, FuturesState] = {}

    def register(self, contract: ContractSpec) -> FuturesState:
        state = FuturesState(contract=contract)
        self._states[contract.security_id] = state
        return state

    def state(self, security_id: str) -> Optional[FuturesState]:
        return self._states.get(security_id)

    def ingest(self, quote: FuturesQuote) -> FuturesState:
        state = self._states.get(quote.security_id)
        if state is None:
            raise KeyError(f"unregistered futures contract: {quote.security_id}")
        self._validate_quote(quote)

        if state.last_quote is not None:
            prev = state.last_quote
            if quote.timestamp < prev.timestamp:
                state.rejected_quotes += 1
                raise ValueError("quote timestamp moved backwards")
            if quote.open_interest is not None and state.previous_oi is not None:
                state.oi_change = quote.open_interest - state.previous_oi
            if quote.volume is not None and state.previous_volume is not None:
                state.volume_change = quote.volume - state.previous_volume
            if quote.ltp != prev.ltp:
                state.realized_mtm = (quote.ltp - prev.ltp) * state.contract.multiplier * state.contract.lot_size
        if quote.previous_close is not None:
            state.basis = quote.ltp - quote.previous_close

        state.previous_oi = quote.open_interest
        state.previous_volume = quote.volume
        state.previous_ltp = quote.ltp
        state.last_quote = quote
        return state

    @staticmethod
    def notional(contract: ContractSpec, price: Decimal) -> Decimal:
        if price <= 0:
            raise ValueError("price must be positive")
        return price * contract.lot_size * contract.multiplier

    @staticmethod
    def tick_value(contract: ContractSpec) -> Decimal:
        return contract.tick_size * contract.lot_size * contract.multiplier

    @staticmethod
    def mark_to_market(contract: ContractSpec, entry: Decimal, mark: Decimal, quantity_lots: int) -> Decimal:
        if entry <= 0 or mark <= 0:
            raise ValueError("entry and mark must be positive")
        if quantity_lots == 0:
            return Decimal("0")
        return (mark - entry) * contract.lot_size * contract.multiplier * quantity_lots

    @staticmethod
    def spread(contract: ContractSpec, quote: FuturesQuote) -> Optional[Decimal]:
        if quote.bid is None or quote.ask is None:
            return None
        if quote.bid <= 0 or quote.ask <= 0 or quote.ask < quote.bid:
            raise ValueError("invalid bid/ask")
        return quote.ask - quote.bid

    @staticmethod
    def _validate_quote(quote: FuturesQuote) -> None:
        if not quote.security_id:
            raise ValueError("quote security_id is required")
        if quote.ltp <= 0:
            raise ValueError("LTP must be positive")
        if quote.volume is not None and quote.volume < 0:
            raise ValueError("volume cannot be negative")
        if quote.open_interest is not None and quote.open_interest < 0:
            raise ValueError("open interest cannot be negative")
        if quote.bid is not None and quote.bid <= 0:
            raise ValueError("bid must be positive")
        if quote.ask is not None and quote.ask <= 0:
            raise ValueError("ask must be positive")
        if quote.bid is not None and quote.ask is not None and quote.ask < quote.bid:
            raise ValueError("crossed market")

    def snapshot(self) -> dict[str, dict]:
        return {sid: asdict(state) for sid, state in self._states.items()}
