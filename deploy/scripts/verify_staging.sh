#!/usr/bin/env bash
set -euo pipefail
ROOT=/opt/cybernetics-engine
SERVICE=cybernetics-engine
ENV_FILE=/etc/cybernetics-engine/cybernetics-engine.env

sudo test -f "$ENV_FILE"
sudo grep -Eq '^CYBERNETICS_ENV=staging$' "$ENV_FILE"
sudo grep -Eq '^CYBERNETICS_TRADING_MODE=paper$' "$ENV_FILE"
sudo grep -Eq '^CYBERNETICS_ORDER_SUBMISSION_ENABLED=false$' "$ENV_FILE"

sudo -u cybernetics "$ROOT/venv/bin/cybernetics-engine" --self-check
sudo systemctl is-enabled --quiet "$SERVICE"
sudo systemctl is-active --quiet "$SERVICE"

snapshot=$(sudo -u cybernetics "$ROOT/venv/bin/cybernetics-engine" --self-check)
python3 - "$snapshot" <<'PY'
import json, sys
payload=json.loads(sys.argv[1])
assert payload["new_trades_allowed"] is False, payload
assert payload.get("trading_mode") == "paper", payload
print("STAGING_SAFE: trading_mode=paper new_trades_allowed=false")
PY
