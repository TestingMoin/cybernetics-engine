# Chunk 125 — Hostinger Environment Preflight

This is the final read-only gate before executing the staging installer on the actual Hostinger Ubuntu VPS.

## Run from the operator machine

```bash
VPS_HOST=<HOSTINGER_PUBLIC_IP> \\
VPS_USER=traderadmin \\
./deploy/scripts/hostinger_preflight.sh
```

The check is intentionally read-only. It only verifies SSH connectivity and the expected operating-system, account, filesystem, Python/systemd, and (when already present) staging safety conditions.

It does **not**:

- install packages
- create or delete directories
- modify systemd
- change permissions
- read or print secrets
- connect to Dhan
- submit orders
- modify PostgreSQL
- enable live trading

A successful preflight is necessary but is **not** proof that the trading engine is operational. The next operator step is the explicit staging installation from Chunk 124/125, followed by service and paper-mode verification.
