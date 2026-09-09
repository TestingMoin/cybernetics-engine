#!/usr/bin/env bash
set -euo pipefail

ROOT=/opt/cybernetics-engine
SERVICE_DIR=/etc/cybernetics-engine
SERVICE=cybernetics-engine
RELEASE="${1:-}"

if [[ -z "$RELEASE" ]]; then
  echo "usage: install_staging.sh /opt/cybernetics-engine/releases/<release>" >&2
  exit 2
fi
if [[ ! -d "$RELEASE" ]]; then
  echo "release directory not found: $RELEASE" >&2
  exit 2
fi
if [[ ! -f "$RELEASE/pyproject.toml" ]]; then
  echo "release is not a valid project (pyproject.toml missing)" >&2
  exit 2
fi
if [[ ! -f "$RELEASE/deploy/systemd/cybernetics-engine.service" ]]; then
  echo "release is missing systemd unit" >&2
  exit 2
fi

if ! id cybernetics >/dev/null 2>&1; then
  echo "required system user cybernetics is missing" >&2
  exit 3
fi

if [[ ! -x "$ROOT/venv/bin/cybernetics-engine" ]]; then
  echo "venv executable not present; create the venv and install the wheel before starting the service" >&2
  exit 4
fi

ENV_FILE="$SERVICE_DIR/cybernetics-engine.env"
if [[ ! -f "$ENV_FILE" ]]; then
  echo "staging environment file missing: $ENV_FILE" >&2
  echo "create it from deploy/config/cybernetics-engine.env.example and keep trading in paper mode" >&2
  exit 5
fi

# Refuse installation unless the persisted environment is explicitly staging/paper safe.
required_pairs=(
  "CYBERNETICS_ENV=staging"
  "CYBERNETICS_TRADING_MODE=paper"
  "CYBERNETICS_ORDER_SUBMISSION_ENABLED=false"
)
for pair in "${required_pairs[@]}"; do
  if ! sudo grep -Eq "^${pair}$" "$ENV_FILE"; then
    echo "unsafe staging environment: missing exact setting ${pair}" >&2
    exit 6
  fi
done

sudo install -d -o cybernetics -g cybernetics "$ROOT/logs" "$ROOT/backups" "$ROOT/staging" "$ROOT/secrets"
sudo install -d -o root -g cybernetics -m 0750 "$SERVICE_DIR"
sudo install -m 0644 "$RELEASE/deploy/systemd/cybernetics-engine.service" "/etc/systemd/system/${SERVICE}.service"

# Preserve the existing environment file; never overwrite secrets/configuration during release install.
sudo chown root:cybernetics "$ENV_FILE"
sudo chmod 0640 "$ENV_FILE"

CURRENT="$ROOT/current"
NEXT="$ROOT/current.next"
PREVIOUS="$ROOT/current.previous"
sudo rm -rf "$NEXT"
sudo cp -a "$RELEASE" "$NEXT"
sudo chown -R cybernetics:cybernetics "$NEXT"

# Keep one rollback copy and switch atomically at directory-name level.
sudo rm -rf "$PREVIOUS"
if [[ -e "$CURRENT" || -L "$CURRENT" ]]; then
  sudo mv "$CURRENT" "$PREVIOUS"
fi
sudo mv "$NEXT" "$CURRENT"

sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE"
sudo systemctl stop "$SERVICE" || true

# Validate the installed release before allowing systemd to start it.
sudo -u cybernetics "$ROOT/venv/bin/cybernetics-engine" --self-check

sudo systemctl start "$SERVICE"
sudo systemctl is-active --quiet "$SERVICE"
sudo systemctl --no-pager --full status "$SERVICE"
