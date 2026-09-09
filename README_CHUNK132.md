# Chunk 132 — Dhan V2 Read-Only Runtime Boundary

This chunk wires the existing Dhan architecture into the canonical runtime without enabling order submission.

## Included
- Secure file-based loading of `dhan_client_id` and `dhan_access_token` from the engine secret directory.
- Stdlib HTTPS transport for Dhan V2 read-only calls.
- `/v2/profile` health probe with bounded caching.
- Read-only `/v2/positions` and `/v2/orders` broker reads.
- Canonical `BrokerRuntimeWiring` injection from `main.py` when both secrets are present.
- Hard-blocked `place_order()` and `cancel_order()` in this adapter.
- Existing paper/live authorization gates remain unchanged.

## Secret files
Create only on the VPS, owned by `cybernetics`, mode `0600`:
- `/opt/cybernetics-engine/secrets/dhan_client_id`
- `/opt/cybernetics-engine/secrets/dhan_access_token`

Do not commit, archive, print, or paste their contents into chat.

## Current safety boundary
- `CYBERNETICS_TRADING_MODE=paper`
- `CYBERNETICS_ORDER_SUBMISSION_ENABLED=false`
- No Dhan POST/PUT/DELETE trading operation is called by this chunk.
- WebSocket live-feed runtime remains a separate next step.
