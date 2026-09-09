# Chunk 122 — Hostinger Staging Installation Runbook

This runbook performs the **first real Ubuntu staging installation**. It is deliberately paper-only.

## Safety gate

Before installation, `/etc/cybernetics-engine/cybernetics-engine.env` must contain exactly:

```text
CYBERNETICS_ENV=staging
CYBERNETICS_TRADING_MODE=paper
CYBERNETICS_ORDER_SUBMISSION_ENABLED=false
```

The installer refuses to start when those settings are absent or unsafe.

## Installation

1. Upload and extract the release under `/opt/cybernetics-engine/releases/<release-id>`.
2. Ensure `/opt/cybernetics-engine/venv/bin/cybernetics-engine` exists and is installed from the release.
3. Create `/etc/cybernetics-engine/cybernetics-engine.env` from the packaged example and preserve the paper-only settings.
4. Run:

```bash
sudo /opt/cybernetics-engine/releases/<release-id>/deploy/scripts/install_staging.sh \
  /opt/cybernetics-engine/releases/<release-id>
```

5. Verify:

```bash
sudo /opt/cybernetics-engine/current/deploy/scripts/verify_staging.sh
sudo systemctl status cybernetics-engine --no-pager
sudo journalctl -u cybernetics-engine -n 100 --no-pager
```

## Rollback

The installer keeps the previous release at:

```text
/opt/cybernetics-engine/current.previous
```

Do not delete the previous release until the current staging build passes acceptance.

## Acceptance gate

Staging is accepted only when:

- systemd is `active` and `enabled`;
- CLI self-check succeeds;
- logs show normal supervisory cycles;
- `CYBERNETICS_TRADING_MODE=paper`;
- `CYBERNETICS_ORDER_SUBMISSION_ENABLED=false`;
- `new_trades_allowed=false`.

No live authorization or broker order submission is part of this procedure.
