# Chunk 120 — Hostinger VPS Staging Deployment

This deployment bundle is **staging-safe**. It is designed for the existing Hostinger Ubuntu layout:

- `/opt/cybernetics-engine/releases/`
- `/opt/cybernetics-engine/current/`
- `/opt/cybernetics-engine/config/`
- `/opt/cybernetics-engine/logs/`
- `/opt/cybernetics-engine/backups/`
- `/opt/cybernetics-engine/staging/`
- `/opt/cybernetics-engine/secrets/`

The service runs as the existing `cybernetics` system user. The provided environment is paper mode with order submission disabled. Live mode is not configured by this bundle.

## Required VPS preparation

1. Upload this release directory under `/opt/cybernetics-engine/releases/<release-name>/`.
2. Ensure `/opt/cybernetics-engine/venv/` exists and contains the installed release candidate.
3. Copy `cybernetics-engine.env.example` to `/etc/cybernetics-engine/cybernetics-engine.env` and keep paper-safe defaults.
4. Run `install_staging.sh /opt/cybernetics-engine/releases/<release-name>`.
5. Run `verify_staging.sh`.

Do **not** enable live mode, set `CYBERNETICS_ORDER_SUBMISSION_ENABLED=true`, or add live approval until a separate live-readiness gate has been completed.
