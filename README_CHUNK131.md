# Chunk 131 — Canonical PostgreSQL Runtime Integration + Installer Atomic-Switch Fix

This chunk is the next staging gate after Chunk 130.

## Changes
- Adds `runtime/postgres.py` as the concrete PostgreSQL runtime adapter.
- Connects the canonical runtime entrypoint to `CYBERNETICS_POSTGRES_DSN` when configured.
- Performs real PostgreSQL health/schema inspection from the runtime supervisory cycle.
- Exposes `trading_mode` in the self-check payload for staging verification.
- Marks the canonical engine process as RUNNING/STOPPED through lifecycle callbacks.
- Keeps broker/internal order and position reconciliation fail-closed until the Dhan reconciliation boundary is connected.
- Fixes the staging installer bug that could create `current/current.next` when an empty `current` directory existed.

## Safety
- Paper mode remains mandatory for staging.
- No broker order endpoint is called by this chunk.
- PostgreSQL credentials remain in the external environment file and are never logged.
- A reachable PostgreSQL database does not imply trading readiness; recovery, reconciliation, market-data, scanner, watchdog, broker, and live-authorization gates remain independent.
