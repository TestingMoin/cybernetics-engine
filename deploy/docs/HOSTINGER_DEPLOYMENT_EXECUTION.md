# Chunk 123 — Hostinger Deployment Execution Runbook

This chunk is the bridge from the verified offline release candidate to the user's real Hostinger Ubuntu VPS.

## Safety invariant

The first deployment is staging-only:

- `CYBERNETICS_ENV=staging`
- `CYBERNETICS_TRADING_MODE=paper`
- `CYBERNETICS_ORDER_SUBMISSION_ENABLED=false`
- live authorization absent/invalid

Do not upload API secrets into the release archive. Keep secrets only in the VPS-owned secret/config location.

## 1. Transfer

From the operator machine, transfer the Chunk 123 archive to the VPS `staging/` directory. Preserve the SHA256 file and verify it on the VPS before extraction.

Example pattern (replace `<VPS_IP>` and local paths):

```bash
scp cybernetics-engine-v1-chunk123.tar.gz traderadmin@<VPS_IP>:/opt/cybernetics-engine/staging/
scp cybernetics-engine-v1-chunk123.tar.gz.sha256 traderadmin@<VPS_IP>:/opt/cybernetics-engine/staging/
```

## 2. Verify before install

```bash
cd /opt/cybernetics-engine/staging
sha256sum -c cybernetics-engine-v1-chunk123.tar.gz.sha256
```

The checksum must pass before extraction.

## 3. Install using the hardened installer

Use the Chunk 122 installer; do not use the obsolete `setup_vps.sh` from the old n8n package.

```bash
sudo /opt/cybernetics-engine/staging/<release>/deploy/scripts/install_staging.sh
```

The installer must refuse the operation if the persisted staging environment is missing, non-paper, or has order submission enabled.

## 4. Verify systemd

```bash
sudo systemctl status cybernetics-engine --no-pager
sudo systemctl is-enabled cybernetics-engine
sudo journalctl -u cybernetics-engine -n 100 --no-pager
```

## 5. Verify safety

Run the bundled staging verifier and confirm:

```text
new_trades_allowed=false
order_submission_enabled=false
live_authorization=invalid/not enabled
```

## 6. Rollback

If verification fails, stop the service and restore the previous release using `current.previous`. Do not delete the previous release until the new one has passed the full staging verification.

## 7. Do not proceed to live

Passing this deployment does not authorize live trading. The following must still be validated separately:

1. PostgreSQL staging connectivity and migrations.
2. Dhan authentication/token lifecycle.
3. Dhan market feed and reconnect/recovery.
4. Instrument/universe synchronization.
5. Full scanner → signal → strategy → risk → paper execution flow.
6. Exit manager, partial profit booking, stop/target/trailing behavior.
7. Restart/recovery/reconciliation drills.
8. PWA/Telegram operational controls.
9. Paper soak test and live-readiness audit.
10. Explicit human live authorization.
