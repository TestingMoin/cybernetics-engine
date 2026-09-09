#!/usr/bin/env bash
set -euo pipefail
ROOT=/opt/cybernetics-engine
SERVICE=cybernetics-engine
fail(){ echo "PREFLIGHT_FAIL: $*" >&2; exit 1; }
id cybernetics >/dev/null 2>&1 || fail "system user cybernetics is missing"
command -v python3 >/dev/null 2>&1 || fail "python3 is missing"
[[ -x "$ROOT/venv/bin/python" ]] || fail "missing $ROOT/venv; create it before install"
[[ -x "$ROOT/venv/bin/cybernetics-engine" ]] || fail "missing installed cybernetics-engine CLI"
[[ -f "$ROOT/current/deploy/systemd/cybernetics-engine.service" ]] || fail "current release is missing systemd unit"
[[ -f "/etc/cybernetics-engine/cybernetics-engine.env" ]] || fail "staging env file missing"
if grep -Eq '(^|_)(KEY|SECRET|TOKEN|PASSWORD|PIN|TOTP)[A-Z_]*=' /etc/cybernetics-engine/cybernetics-engine.env; then
  echo "PREFLIGHT_NOTE: secret-bearing env detected; values are not printed"
fi
snapshot=$(sudo -u cybernetics "$ROOT/venv/bin/cybernetics-engine" --self-check)
python3 - "$snapshot" <<'PY'
import json, sys
p=json.loads(sys.argv[1])
assert p.get('new_trades_allowed') is False, p
assert p.get('live_authorization_valid') in (False, None), p
print('PREFLIGHT_SAFE: new_trades_allowed=false')
PY
echo "PREFLIGHT_OK"
