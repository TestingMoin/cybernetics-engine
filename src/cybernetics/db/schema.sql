-- Cybernetics Trading Engine — authoritative PostgreSQL schema baseline.
-- All production table/index DDL is owned here. Runtime modules must not
-- create persistent tables independently.

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS engine_events (
    event_id UUID PRIMARY KEY,
    event_ts TIMESTAMPTZ NOT NULL,
    event_type TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'INFO',
    source TEXT NOT NULL,
    correlation_id UUID,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_engine_events_ts ON engine_events(event_ts);
CREATE INDEX IF NOT EXISTS idx_engine_events_type ON engine_events(event_type);

CREATE TABLE IF NOT EXISTS market_events (
    event_id UUID PRIMARY KEY,
    event_ts TIMESTAMPTZ NOT NULL,
    exchange TEXT NOT NULL,
    segment TEXT NOT NULL,
    instrument TEXT NOT NULL,
    security_id BIGINT,
    event_type TEXT NOT NULL,
    price NUMERIC,
    volume NUMERIC,
    oi NUMERIC,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_market_events_instrument_ts
ON market_events(instrument, event_ts);

CREATE TABLE IF NOT EXISTS signal_events (
    signal_id UUID PRIMARY KEY,
    signal_ts TIMESTAMPTZ NOT NULL,
    exchange TEXT NOT NULL,
    scanner_id TEXT NOT NULL,
    instrument TEXT NOT NULL,
    underlying TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    side TEXT NOT NULL,
    source TEXT NOT NULL,
    score NUMERIC NOT NULL,
    confidence NUMERIC NOT NULL,
    regime TEXT,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    invalidations JSONB NOT NULL DEFAULT '[]'::jsonb,
    ttl_seconds NUMERIC NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_signal_events_underlying_ts
ON signal_events(underlying, signal_ts);

CREATE TABLE IF NOT EXISTS strategy_decisions (
    decision_id UUID PRIMARY KEY,
    decision_ts TIMESTAMPTZ NOT NULL,
    strategy_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    action TEXT NOT NULL,
    side TEXT,
    reason TEXT NOT NULL,
    score NUMERIC,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS risk_decisions (
    decision_id UUID PRIMARY KEY,
    decision_ts TIMESTAMPTZ NOT NULL,
    strategy_id TEXT,
    symbol TEXT NOT NULL,
    approved BOOLEAN NOT NULL,
    requested_quantity BIGINT NOT NULL,
    allowed_quantity BIGINT NOT NULL,
    reasons JSONB NOT NULL DEFAULT '[]'::jsonb,
    exposure_after NUMERIC,
    margin_required NUMERIC
);

CREATE TABLE IF NOT EXISTS orders (
    order_id UUID PRIMARY KEY,
    parent_order_id UUID,
    client_order_key TEXT,
    broker_order_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    requested_quantity BIGINT NOT NULL,
    filled_quantity BIGINT NOT NULL DEFAULT 0,
    remaining_quantity BIGINT NOT NULL,
    order_type TEXT NOT NULL,
    limit_price NUMERIC,
    stop_price NUMERIC,
    avg_fill_price NUMERIC,
    status TEXT NOT NULL,
    reject_reason TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_orders_client_order_key
ON orders(client_order_key) WHERE client_order_key IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS ux_orders_broker_order_id
ON orders(broker_order_id) WHERE broker_order_id IS NOT NULL;

-- Durable client-order idempotency is intentionally separate from the full
-- orders ledger. This prevents a partial idempotency row from violating the
-- orders table's NOT NULL trade fields.
CREATE TABLE IF NOT EXISTS order_idempotency (
    client_order_key TEXT PRIMARY KEY,
    broker_order_id TEXT,
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_order_idempotency_broker_order_id
ON order_idempotency(broker_order_id) WHERE broker_order_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_orders_symbol_created ON orders(symbol, created_at);
CREATE INDEX IF NOT EXISTS idx_orders_parent ON orders(parent_order_id);
CREATE INDEX IF NOT EXISTS idx_orders_broker_order_id ON orders(broker_order_id);

CREATE TABLE IF NOT EXISTS order_events (
    seq BIGSERIAL PRIMARY KEY,
    order_id UUID NOT NULL,
    event_ts TIMESTAMPTZ NOT NULL,
    event_type TEXT NOT NULL,
    status TEXT NOT NULL,
    details JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_order_events_order_ts
ON order_events(order_id, event_ts);

CREATE TABLE IF NOT EXISTS fills (
    fill_id UUID PRIMARY KEY,
    order_id UUID NOT NULL,
    fill_ts TIMESTAMPTZ NOT NULL,
    quantity BIGINT NOT NULL,
    price NUMERIC NOT NULL,
    fee NUMERIC NOT NULL DEFAULT 0,
    slippage NUMERIC NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS positions (
    symbol TEXT PRIMARY KEY,
    updated_at TIMESTAMPTZ NOT NULL,
    quantity BIGINT NOT NULL,
    avg_price NUMERIC NOT NULL DEFAULT 0,
    realized_pnl NUMERIC NOT NULL DEFAULT 0,
    unrealized_pnl NUMERIC NOT NULL DEFAULT 0,
    fees NUMERIC NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS reconciliation_events (
    reconciliation_id UUID PRIMARY KEY,
    event_ts TIMESTAMPTZ NOT NULL,
    matched BOOLEAN NOT NULL,
    no_new_trades BOOLEAN NOT NULL,
    issues JSONB NOT NULL DEFAULT '[]'::jsonb
);

CREATE TABLE IF NOT EXISTS health_events (
    health_id UUID PRIMARY KEY,
    event_ts TIMESTAMPTZ NOT NULL,
    component TEXT NOT NULL,
    health TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT '',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS ai_observations (
    observation_id UUID PRIMARY KEY,
    observed_at TIMESTAMPTZ NOT NULL,
    scope TEXT NOT NULL,
    observation_type TEXT NOT NULL,
    summary TEXT NOT NULL,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS ai_proposals (
    proposal_id UUID PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL,
    observation_id UUID,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    current_version TEXT,
    proposed_version TEXT,
    rationale TEXT NOT NULL,
    tests_required JSONB NOT NULL DEFAULT '[]'::jsonb,
    status TEXT NOT NULL DEFAULT 'PROPOSED'
);

CREATE TABLE IF NOT EXISTS software_releases (
    release_id UUID PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL,
    version TEXT NOT NULL,
    git_commit TEXT,
    artifact_sha256 TEXT NOT NULL,
    environment TEXT NOT NULL,
    approved_by TEXT,
    notes TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS fill_ledger (
    fill_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL,
    trade_id TEXT NOT NULL,
    state TEXT NOT NULL CHECK (
        state IN ('CLAIMED','COMPLETED','RECOVERY_REQUIRED')
    ),
    error TEXT NULL,
    claimed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMPTZ NULL
);
CREATE INDEX IF NOT EXISTS idx_fill_ledger_order_id ON fill_ledger(order_id);
CREATE INDEX IF NOT EXISTS idx_fill_ledger_trade_id ON fill_ledger(trade_id);

CREATE TABLE IF NOT EXISTS fill_outbox (
    event_id TEXT PRIMARY KEY,
    fill_id TEXT NOT NULL,
    order_id TEXT NOT NULL,
    trade_id TEXT NOT NULL,
    payload_json JSONB NOT NULL,
    state TEXT NOT NULL CHECK (
        state IN ('PENDING','PROCESSING','COMPLETED','FAILED')
    ),
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMPTZ NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_fill_outbox_fill_id ON fill_outbox(fill_id);
CREATE INDEX IF NOT EXISTS idx_fill_outbox_state ON fill_outbox(state);

CREATE TABLE IF NOT EXISTS control_command_audit (
    command_id TEXT PRIMARY KEY,
    command TEXT NOT NULL,
    source TEXT NOT NULL,
    result TEXT NOT NULL CHECK (
        result IN ('ACCEPTED','DUPLICATE','REJECTED','STALE')
    ),
    state TEXT NOT NULL,
    reason TEXT NOT NULL,
    issued_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_control_command_audit_issued_at
ON control_command_audit(issued_at);
CREATE INDEX IF NOT EXISTS idx_control_command_audit_source
ON control_command_audit(source);
CREATE INDEX IF NOT EXISTS idx_control_command_audit_result
ON control_command_audit(result);

CREATE TABLE IF NOT EXISTS emergency_control_state (
    control_key TEXT PRIMARY KEY,
    active BOOLEAN NOT NULL,
    emergency_id TEXT NULL,
    reason TEXT NULL,
    actor TEXT NULL,
    issued_at TIMESTAMPTZ NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_emergency_control_active
ON emergency_control_state(active);

CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
