from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Mapping
from uuid import uuid4

from cybernetics.brokers.interface import BrokerAdapter


@dataclass(frozen=True)
class DhanOrderIdentity:
    correlation_id: str | None
    broker_order_id: str | None


@dataclass(frozen=True)
class DhanReconciliationReport:
    matched: bool
    orders_reconciled: bool
    positions_reconciled: bool
    issues: tuple[dict[str, Any], ...]
    source_counts: dict[str, int]

    @property
    def no_new_trades(self) -> bool:
        return not self.matched

    def fingerprint(self) -> str:
        payload = {
            "matched": self.matched,
            "orders_reconciled": self.orders_reconciled,
            "positions_reconciled": self.positions_reconciled,
            "issues": self.issues,
            "source_counts": self.source_counts,
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))


@dataclass
class DhanPostgresReconciliationAdapter:
    """Read-only Dhan↔PostgreSQL reconciliation boundary.

    It never mutates Dhan. It only reads Dhan orders/positions and the internal
    PostgreSQL ledgers, then writes an append-only reconciliation audit event.

    Position identity is deliberately conservative: the current internal
    positions schema stores only ``symbol``, while Dhan exposes
    ``exchangeSegment`` + ``securityId``. Pre-existing non-flat broker
    positions are quarantined as out-of-scope handoff state and still block
    full position reconciliation until they are explicitly adopted or cleared.
    """

    broker: BrokerAdapter
    connection_factory: Any
    reconciliation_cache_seconds: float = 10.0
    owned_correlation_prefix: str = "CTE-"

    def __post_init__(self) -> None:
        if self.reconciliation_cache_seconds <= 0:
            raise ValueError("reconciliation_cache_seconds_must_be_positive")
        if not self.owned_correlation_prefix:
            raise ValueError("owned_correlation_prefix_required")
        self._cache_until = 0.0
        self._cache: DhanReconciliationReport | None = None
        self._last_persisted_fingerprint: str | None = None
        import time
        self._clock = time.monotonic

    def reconcile(self) -> DhanReconciliationReport:
        now = self._clock()
        if self._cache is not None and now < self._cache_until:
            return self._cache

        issues: list[dict[str, Any]] = []
        try:
            broker_orders = self.broker.get_orders()
            broker_positions = self.broker.get_positions()
        except Exception as exc:
            report = DhanReconciliationReport(
                matched=False,
                orders_reconciled=False,
                positions_reconciled=False,
                issues=({"kind": "BROKER_READ_FAILED", "severity": "CRITICAL", "reason": type(exc).__name__},),
                source_counts={"broker_orders": 0, "broker_positions": 0, "internal_orders": 0, "internal_positions": 0},
            )
            self._cache = report
            self._cache_until = now + self.reconciliation_cache_seconds
            self._persist(report)
            return report

        connection = self.connection_factory()
        try:
            internal_orders = connection.execute(
                """
                SELECT order_id::text, client_order_key, broker_order_id, symbol, side,
                       requested_quantity, filled_quantity, avg_fill_price, status
                FROM orders
                ORDER BY created_at, order_id
                """
            ).fetchall()
            internal_positions = connection.execute(
                """
                SELECT symbol, quantity, avg_price
                FROM positions
                ORDER BY symbol
                """
            ).fetchall()
        finally:
            connection.close()

        order_issues = self._reconcile_orders(internal_orders, broker_orders, owned_correlation_prefix=self.owned_correlation_prefix)
        position_issues = self._reconcile_positions(internal_positions, broker_positions)
        issues.extend(order_issues)
        issues.extend(position_issues)

        report = DhanReconciliationReport(
            matched=not issues,
            orders_reconciled=not order_issues,
            positions_reconciled=not position_issues,
            issues=tuple(issues),
            source_counts={
                "broker_orders": len(broker_orders),
                "broker_positions": len(broker_positions),
                "internal_orders": len(internal_orders),
                "internal_positions": len(internal_positions),
            },
        )
        self._cache = report
        self._cache_until = now + self.reconciliation_cache_seconds
        self._persist(report)
        return report

    @staticmethod
    def _reconcile_orders(internal_rows: list[tuple[Any, ...]], broker_rows: list[Mapping[str, Any]], *, owned_correlation_prefix: str = "CTE-") -> list[dict[str, Any]]:
        by_client: dict[str, tuple[Any, ...]] = {}
        by_broker: dict[str, tuple[Any, ...]] = {}
        for row in internal_rows:
            order_id, client_key, broker_id, *_ = row
            if client_key:
                by_client[str(client_key)] = row
            if broker_id:
                by_broker[str(broker_id)] = row

        issues: list[dict[str, Any]] = []
        for raw in broker_rows:
            correlation = str(raw.get("correlationId")) if raw.get("correlationId") is not None else None
            broker_id = str(raw.get("orderId")) if raw.get("orderId") is not None else None
            internal = by_client.get(correlation or "") or by_broker.get(broker_id or "")
            key = correlation or broker_id or "UNKNOWN"

            # Initial adoption boundary: only broker orders explicitly owned by
            # Cybernetics are reconciliation candidates. Pre-existing/manual
            # Dhan orders are outside the engine's ledger and must not create a
            # false reconciliation failure merely because the internal ledger is
            # intentionally empty at first deployment.
            owned = bool(correlation and correlation.startswith(owned_correlation_prefix))
            if internal is None and not owned:
                continue
            if internal is None:
                issues.append({
                    "kind": "OWNED_BROKER_ORDER_MISSING_INTERNAL",
                    "severity": "CRITICAL",
                    "key": key,
                    "reason": "cybernetics_owned_broker_order_absent_in_internal_state",
                })
                continue

            order_id, client_key, stored_broker_id, symbol, side, requested_qty, filled_qty, avg_fill, status = internal
            checks = [
                ("ORDER_METADATA_MISMATCH", str(symbol) == str(raw.get("tradingSymbol")), "symbol_mismatch"),
                ("ORDER_SIDE_MISMATCH", str(side).upper() == str(raw.get("transactionType", "")).upper(), "side_mismatch"),
                ("ORDER_QUANTITY_MISMATCH", int(requested_qty) == int(raw.get("quantity", 0)), "quantity_mismatch"),
                ("FILL_QUANTITY_MISMATCH", int(filled_qty) == int(raw.get("filledQty", 0)), "filled_quantity_mismatch"),
                ("STATUS_MISMATCH", str(status).upper() == str(raw.get("orderStatus", "")).upper(), "status_mismatch"),
            ]
            if avg_fill is not None and raw.get("averageTradedPrice") is not None:
                checks.append(("AVG_PRICE_MISMATCH", abs(float(avg_fill) - float(raw["averageTradedPrice"])) <= 1e-9, "average_fill_price_mismatch"))
            if stored_broker_id and broker_id and str(stored_broker_id) != broker_id:
                checks.append(("BROKER_ID_MISMATCH", False, "stored_broker_order_id_mismatch"))
            if client_key and correlation and str(client_key) != correlation:
                checks.append(("CLIENT_KEY_MISMATCH", False, "client_order_key_mismatch"))

            for kind, ok, reason in checks:
                if not ok:
                    issues.append({"kind": kind, "severity": "HIGH", "key": str(order_id), "reason": reason})
        return issues

    @staticmethod
    def _reconcile_positions(internal_rows: list[tuple[Any, ...]], broker_rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
        internal = {str(row[0]): row for row in internal_rows}
        issues: list[dict[str, Any]] = []

        broker_by_symbol: dict[str, list[Mapping[str, Any]]] = {}
        for raw in broker_rows:
            symbol = str(raw.get("tradingSymbol") or "")
            broker_by_symbol.setdefault(symbol, []).append(raw)

        for symbol, rows in broker_by_symbol.items():
            # Dhan can return duplicate rows for the same instrument identity.
            # Never select rows[0] blindly: a zero-quantity duplicate can hide
            # a simultaneously returned non-zero position and falsely clear
            # reconciliation. Different identities sharing one trading symbol
            # remain a hard ambiguity.
            identities = {(str(r.get("exchangeSegment")), str(r.get("securityId"))) for r in rows}
            if len(identities) > 1:
                issues.append({
                    "kind": "POSITION_IDENTITY_AMBIGUOUS",
                    "severity": "CRITICAL",
                    "key": symbol,
                    "reason": "multiple_dhan_instrument_identities_share_symbol",
                })
                continue

            nonzero_rows = [r for r in rows if int(r.get("netQty", 0) or 0) != 0]
            if len(nonzero_rows) > 1:
                quantities = {int(r.get("netQty", 0) or 0) for r in nonzero_rows}
                if len(quantities) > 1:
                    issues.append({
                        "kind": "POSITION_DUPLICATE_CONFLICT",
                        "severity": "CRITICAL",
                        "key": symbol,
                        "reason": "duplicate_dhan_position_rows_have_conflicting_nonzero_quantities",
                    })
                    continue

            raw = nonzero_rows[0] if nonzero_rows else rows[0]
            net_qty = int(raw.get("netQty", 0) or 0)
            if symbol not in internal:
                if net_qty != 0:
                    # A non-flat broker position that predates Cybernetics
                    # ownership is deliberately quarantined. It is not treated
                    # as an engine mismatch, but it still blocks full position
                    # reconciliation because the current internal schema cannot
                    # safely represent/adopt the broker instrument identity.
                    issues.append({
                        "kind": "PREEXISTING_BROKER_POSITION",
                        "severity": "HIGH",
                        "key": symbol,
                        "reason": "broker_position_exists_before_cybernetics_ownership",
                        "security_id": str(raw.get("securityId") or ""),
                        "exchange_segment": str(raw.get("exchangeSegment") or ""),
                    })
                continue

            _, quantity, avg_price = internal[symbol]
            if net_qty != int(quantity):
                issues.append({"kind": "POSITION_QUANTITY_MISMATCH", "severity": "CRITICAL", "key": symbol, "reason": "position_quantity_differs"})
            broker_cost = raw.get("costPrice")
            if broker_cost is not None and abs(float(avg_price) - float(broker_cost)) > 0.01:
                issues.append({"kind": "POSITION_PRICE_MISMATCH", "severity": "HIGH", "key": symbol, "reason": "position_average_price_differs"})
            # Current internal schema has no segment/security-id columns.
            issues.append({
                "kind": "POSITION_IDENTITY_UNVERIFIABLE",
                "severity": "CRITICAL",
                "key": symbol,
                "reason": "internal_positions_schema_lacks_security_id_and_exchange_segment",
                "security_id": str(raw.get("securityId") or ""),
                "exchange_segment": str(raw.get("exchangeSegment") or ""),
            })

        for symbol, row in internal.items():
            if symbol not in broker_by_symbol and int(row[1]) != 0:
                issues.append({"kind": "MISSING_BROKER_POSITION", "severity": "CRITICAL", "key": symbol, "reason": "internal_position_absent_at_broker"})
        return issues

    def _persist(self, report: DhanReconciliationReport) -> None:
        fingerprint = report.fingerprint()
        if fingerprint == self._last_persisted_fingerprint:
            return
        connection = self.connection_factory()
        try:
            connection.execute(
                """
                INSERT INTO reconciliation_events
                    (reconciliation_id, event_ts, matched, no_new_trades, issues)
                VALUES (%s, CURRENT_TIMESTAMP, %s, %s, %s::jsonb)
                """,
                (str(uuid4()), report.matched, report.no_new_trades, json.dumps(report.issues, sort_keys=True)),
            )
            connection.commit()
            self._last_persisted_fingerprint = fingerprint
        finally:
            connection.close()
