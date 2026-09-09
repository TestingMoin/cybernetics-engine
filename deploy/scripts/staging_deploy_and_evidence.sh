#!/usr/bin/env bash
set -euo pipefail
: "${VPS_HOST:?Set VPS_HOST}"
VPS_USER="${VPS_USER:-traderadmin}"
REMOTE_TAG="${REMOTE_TAG:-chunk127}"
ROOT="/opt/cybernetics-engine"
CONFIRM="${CYBERNETICS_STAGING_CONFIRM:-}"
LOCAL_ARCHIVE="${1:-}"
[[ "$CONFIRM" == "INSTALL_STAGING_ONLY" ]] || { echo "BLOCKED: set CYBERNETICS_STAGING_CONFIRM=INSTALL_STAGING_ONLY" >&2; exit 20; }
[[ -f "$LOCAL_ARCHIVE" ]] || { echo "usage: $0 <release.tar.gz>" >&2; exit 2; }
[[ "$LOCAL_ARCHIVE" == *.tar.gz ]] || { echo "release must be .tar.gz" >&2; exit 2; }
[[ -f "${LOCAL_ARCHIVE}.sha256" ]] || { echo "missing checksum" >&2; exit 3; }
sha256sum -c "${LOCAL_ARCHIVE}.sha256"
SSH_OPTS=(-o BatchMode=yes -o ConnectTimeout=10 -o ServerAliveInterval=15 -o ServerAliveCountMax=2)
REMOTE_BASE="${ROOT}/staging/${REMOTE_TAG}"
ARCHIVE_NAME="$(basename "$LOCAL_ARCHIVE")"
EVIDENCE_DIR="${REMOTE_BASE}/evidence"
ssh "${SSH_OPTS[@]}" "${VPS_USER}@${VPS_HOST}" "mkdir -p '$REMOTE_BASE'"
scp "${SSH_OPTS[@]}" "$LOCAL_ARCHIVE" "${VPS_USER}@${VPS_HOST}:${REMOTE_BASE}/${ARCHIVE_NAME}"
scp "${SSH_OPTS[@]}" "${LOCAL_ARCHIVE}.sha256" "${VPS_USER}@${VPS_HOST}:${REMOTE_BASE}/${ARCHIVE_NAME}.sha256"
ssh "${SSH_OPTS[@]}" "${VPS_USER}@${VPS_HOST}" bash -s -- "$REMOTE_BASE" "$ARCHIVE_NAME" "$EVIDENCE_DIR" <<'REMOTE'
set -euo pipefail
BASE="$1"; ARCHIVE="$2"; EVIDENCE="$3"
mkdir -p "$EVIDENCE"
exec > >(tee "$EVIDENCE/deploy-transcript.txt") 2>&1
echo "=== CYBERNETICS CHUNK 127 STAGING DEPLOY ==="
date -Is
sha256sum -c "$BASE/$ARCHIVE.sha256"
rm -rf "$BASE/extracted"; mkdir -p "$BASE/extracted"
tar -xzf "$BASE/$ARCHIVE" -C "$BASE/extracted"
RELEASE_DIR="$(find "$BASE/extracted" -mindepth 1 -maxdepth 1 -type d -print -quit)"
test -n "$RELEASE_DIR"
test -f "$RELEASE_DIR/pyproject.toml"
test -f "$RELEASE_DIR/deploy/scripts/install_staging.sh"
test -f /etc/cybernetics-engine/cybernetics-engine.env
grep -Eq '^CYBERNETICS_ENV=staging$' /etc/cybernetics-engine/cybernetics-engine.env
grep -Eq '^CYBERNETICS_TRADING_MODE=paper$' /etc/cybernetics-engine/cybernetics-engine.env
grep -Eq '^CYBERNETICS_ORDER_SUBMISSION_ENABLED=false$' /etc/cybernetics-engine/cybernetics-engine.env
echo "=== HOST PREFLIGHT ==="
sudo "$RELEASE_DIR/deploy/scripts/hostinger_preflight.sh" | tee "$EVIDENCE/host-preflight.txt"
echo "=== INSTALL STAGING ==="
sudo "$RELEASE_DIR/deploy/scripts/install_staging.sh" "$RELEASE_DIR"
echo "=== VERIFY STAGING ==="
sudo "$RELEASE_DIR/deploy/scripts/verify_staging.sh" | tee "$EVIDENCE/staging-verify.txt"
echo "=== SYSTEMD STATUS ==="
sudo systemctl --no-pager --full status cybernetics-engine.service | tee "$EVIDENCE/systemd-status.txt" || true
echo "=== JOURNAL ==="
sudo journalctl -u cybernetics-engine.service -n 80 --no-pager | tee "$EVIDENCE/journal.txt" || true
echo "=== SELF CHECK ==="
"$ROOT/venv/bin/cybernetics-engine" --self-check | tee "$EVIDENCE/self-check.txt"
grep -Eiq 'new_trades_allowed[^[:alnum:]]*(false|no)' "$EVIDENCE/self-check.txt" || { echo "FATAL: new_trades_allowed not false" >&2; exit 40; }
echo "STAGING_DEPLOYMENT_VERIFIED"
REMOTE
