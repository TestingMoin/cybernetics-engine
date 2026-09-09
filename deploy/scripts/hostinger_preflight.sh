#!/usr/bin/env bash
set -euo pipefail

# Chunk 125 — read-only Hostinger VPS environment preflight.
# No package installation, service activation, file deletion, or secret access.

: "${VPS_HOST:?Set VPS_HOST}"
VPS_USER="${VPS_USER:-traderadmin}"
EXPECTED_ROOT="/opt/cybernetics-engine"

ssh -o BatchMode=yes -o ConnectTimeout=10 "${VPS_USER}@${VPS_HOST}" bash -s -- "$EXPECTED_ROOT" <<'REMOTE'
set -euo pipefail
ROOT="$1"

fail=0
check() {
  local label="$1"; shift
  if "$@" >/dev/null 2>&1; then
    printf 'PASS: %s\n' "$label"
  else
    printf 'FAIL: %s\n' "$label"
    fail=1
  fi
}

printf 'HOSTINGER_PREFLIGHT_BEGIN\n'
printf 'host=%s\n' "$(hostname)"
printf 'user=%s\n' "$(id -un)"
printf 'os=%s\n' "$(. /etc/os-release && printf '%s %s' "$ID" "$VERSION_ID")"

check 'Ubuntu host' bash -c 'test -f /etc/os-release && . /etc/os-release && test "$ID" = ubuntu'
check 'cybernetics system account exists' id cybernetics
check 'staging root exists' test -d "$ROOT/staging"
check 'release root exists' test -d "$ROOT/releases"
check 'config root exists' test -d "$ROOT/config"
check 'logs root exists' test -d "$ROOT/logs"
check 'backups root exists' test -d "$ROOT/backups"
check 'python3 available' command -v python3
check 'systemctl available' command -v systemctl
check 'service file absent or known' bash -c 'test ! -e /etc/systemd/system/cybernetics-engine.service || grep -q "^\[Unit\]" /etc/systemd/system/cybernetics-engine.service'

# Safety checks are intentionally read-only and fail closed.
if [[ -f /etc/cybernetics-engine/cybernetics-engine.env ]]; then
  check 'staging environment' grep -Eq '^CYBERNETICS_ENV=staging$' /etc/cybernetics-engine/cybernetics-engine.env
  check 'paper trading' grep -Eq '^CYBERNETICS_TRADING_MODE=paper$' /etc/cybernetics-engine/cybernetics-engine.env
  check 'order submission disabled' grep -Eq '^CYBERNETICS_ORDER_SUBMISSION_ENABLED=false$' /etc/cybernetics-engine/cybernetics-engine.env
else
  printf 'WARN: staging environment file not yet installed\n'
fi

printf 'HOSTINGER_PREFLIGHT_RESULT=%s\n' "$([ "$fail" -eq 0 ] && echo PASS || echo FAIL)"
printf 'HOSTINGER_PREFLIGHT_END\n'
exit "$fail"
REMOTE
