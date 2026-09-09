#!/usr/bin/env bash
set -euo pipefail

# Chunk 124: operator-side remote Hostinger staging deployment wrapper.
# Safe by construction: refuses non-paper deployment and never carries secrets.

: "${VPS_HOST:?Set VPS_HOST to the Hostinger public IP/hostname}"
VPS_USER="${VPS_USER:-traderadmin}"
SSH_OPTS=( -o BatchMode=yes -o ConnectTimeout=10 )
ROOT="/opt/cybernetics-engine"
LOCAL_ARCHIVE="${1:-}"

if [[ -z "$LOCAL_ARCHIVE" || ! -f "$LOCAL_ARCHIVE" ]]; then
  echo "usage: VPS_HOST=... $0 <chunk123-or-later-release.tar.gz>" >&2
  exit 2
fi

case "$(basename "$LOCAL_ARCHIVE")" in
  *.tar.gz) ;;
  *) echo "release must be .tar.gz" >&2; exit 2;;
esac

if [[ ! -f "${LOCAL_ARCHIVE}.sha256" ]]; then
  echo "missing checksum file: ${LOCAL_ARCHIVE}.sha256" >&2
  exit 3
fi

sha256sum -c "${LOCAL_ARCHIVE}.sha256"

REMOTE_TAG="${REMOTE_TAG:-chunk126}"
REMOTE_BASE="${ROOT}/staging/${REMOTE_TAG}"
ARCHIVE_NAME="$(basename "$LOCAL_ARCHIVE")"
CHECKSUM_NAME="$(basename "${LOCAL_ARCHIVE}.sha256")"

ssh "${SSH_OPTS[@]}" "${VPS_USER}@${VPS_HOST}" "mkdir -p '${REMOTE_BASE}'"
scp "${SSH_OPTS[@]}" "$LOCAL_ARCHIVE" "${VPS_USER}@${VPS_HOST}:${REMOTE_BASE}/${ARCHIVE_NAME}"
scp "${SSH_OPTS[@]}" "${LOCAL_ARCHIVE}.sha256" "${VPS_USER}@${VPS_HOST}:${REMOTE_BASE}/${CHECKSUM_NAME}"

ssh "${SSH_OPTS[@]}" "${VPS_USER}@${VPS_HOST}" bash -s -- "$REMOTE_BASE" "$ARCHIVE_NAME" <<'REMOTE'
set -euo pipefail
REMOTE_BASE="$1"
ARCHIVE_NAME="$2"
cd "$REMOTE_BASE"
sha256sum -c "${ARCHIVE_NAME}.sha256"
rm -rf extracted
mkdir extracted
tar -xzf "$ARCHIVE_NAME" -C extracted
RELEASE_DIR="$(find extracted -mindepth 1 -maxdepth 1 -type d | head -n 1)"
test -n "$RELEASE_DIR"
test -f "$RELEASE_DIR/deploy/scripts/preflight_staging.sh"
test -f "$RELEASE_DIR/deploy/scripts/install_staging.sh"
test -f "$RELEASE_DIR/pyproject.toml"
# Explicitly refuse unsafe environment before invoking the installer.
if [[ ! -f /etc/cybernetics-engine/cybernetics-engine.env ]]; then
  echo "REMOTE_DEPLOY_BLOCKED: staging env file missing" >&2
  exit 10
fi
grep -Eq '^CYBERNETICS_ENV=staging$' /etc/cybernetics-engine/cybernetics-engine.env
grep -Eq '^CYBERNETICS_TRADING_MODE=paper$' /etc/cybernetics-engine/cybernetics-engine.env
grep -Eq '^CYBERNETICS_ORDER_SUBMISSION_ENABLED=false$' /etc/cybernetics-engine/cybernetics-engine.env

echo "REMOTE_TRANSFER_VERIFIED"
echo "REMOTE_STAGING_GUARDS_PASSED"
echo "NEXT_ACTION: run the release installer explicitly after reviewing extracted release"
REMOTE
