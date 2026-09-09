#!/usr/bin/env bash
set -euo pipefail

# Chunk 126 — explicit Hostinger staging installer executor.
# Deliberately requires an operator confirmation token and paper-mode guards.
: "${VPS_HOST:?Set VPS_HOST}"
VPS_USER="${VPS_USER:-traderadmin}"
REMOTE_TAG="${REMOTE_TAG:-chunk126}"
ROOT="/opt/cybernetics-engine"
CONFIRM="${CYBERNETICS_STAGING_CONFIRM:-}"

if [[ "$CONFIRM" != "INSTALL_STAGING_ONLY" ]]; then
  echo "BLOCKED: set CYBERNETICS_STAGING_CONFIRM=INSTALL_STAGING_ONLY to execute staging installation" >&2
  exit 20
fi

ssh_opts=( -o BatchMode=yes -o ConnectTimeout=10 )
ssh "${ssh_opts[@]}" "${VPS_USER}@${VPS_HOST}" bash -s -- "$ROOT/staging/$REMOTE_TAG" <<'REMOTE'
set -euo pipefail
BASE="$1"
test -d "$BASE/extracted"
RELEASE_DIR="$(find "$BASE/extracted" -mindepth 1 -maxdepth 1 -type d -print -quit)"
test -n "$RELEASE_DIR"
test -f "$RELEASE_DIR/deploy/scripts/install_staging.sh"
test -f /etc/cybernetics-engine/cybernetics-engine.env
grep -Eq '^CYBERNETICS_ENV=staging$' /etc/cybernetics-engine/cybernetics-engine.env
grep -Eq '^CYBERNETICS_TRADING_MODE=paper$' /etc/cybernetics-engine/cybernetics-engine.env
grep -Eq '^CYBERNETICS_ORDER_SUBMISSION_ENABLED=false$' /etc/cybernetics-engine/cybernetics-engine.env

# Ensure the target executable exists before invoking the installer.
test -x /opt/cybernetics-engine/venv/bin/cybernetics-engine
sudo "$RELEASE_DIR/deploy/scripts/install_staging.sh" "$RELEASE_DIR"
sudo "$RELEASE_DIR/deploy/scripts/verify_staging.sh"
echo "STAGING_INSTALL_COMPLETE"
REMOTE
