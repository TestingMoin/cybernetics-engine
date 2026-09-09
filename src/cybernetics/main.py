from __future__ import annotations

import argparse
import json
import os

from .config.settings import DeploymentConfig
from .runtime.application import RuntimeApplication, install_signal_handlers
from .runtime.production import build_production_runtime
from .runtime.postgres import PostgreSQLRuntimeAdapter
from .db.staging import PostgreSQLStagingConfig
from .integration.dhan_runtime import build_dhan_read_only_broker
from .runtime.broker import build_broker_runtime_wiring


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cybernetics-engine",
        description="Canonical Cybernetics Trading Engine process entrypoint.",
    )
    parser.add_argument(
        "--self-check",
        action="store_true",
        help="print the fail-closed runtime readiness snapshot and exit",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="start the canonical lifecycle, emit one snapshot, and stop",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=float(os.getenv("CYBERNETICS_RUNTIME_POLL_SECONDS", "1.0")),
        help="process wait interval in seconds",
    )
    return parser


def _snapshot_payload(app: RuntimeApplication, deployment: DeploymentConfig) -> dict[str, object]:
    snapshot = app.snapshot()
    return {
        "service": app.config.service_name,
        "lifecycle": app.lifecycle.value,
        "engine_ready": snapshot.readiness.engine_ready,
        "new_trades_allowed": snapshot.readiness.new_trades_allowed,
        "trading_mode": deployment.trading_mode.value,
        "reasons": list(snapshot.readiness.reasons),
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    deployment = DeploymentConfig.from_env()
    deployment.validate_filesystem()
    dhan_broker = build_dhan_read_only_broker(deployment.secret_dir)
    broker_runtime = build_broker_runtime_wiring(broker=dhan_broker) if dhan_broker is not None else None
    postgres_config = PostgreSQLStagingConfig.from_env()
    postgres_runtime = (
        PostgreSQLRuntimeAdapter(postgres_config, broker=dhan_broker)
        if postgres_config is not None
        else None
    )
    app = build_production_runtime(
        deployment,
        postgres_runtime=postgres_runtime,
        broker_runtime=broker_runtime,
    )

    if args.self_check:
        print(json.dumps(_snapshot_payload(app, deployment), sort_keys=True))
        return 0

    install_signal_handlers(app)
    if args.once:
        app.start()
        try:
            print(json.dumps(_snapshot_payload(app, deployment), sort_keys=True))
            return 0
        finally:
            app.stop()

    return app.run()


if __name__ == "__main__":
    raise SystemExit(main())
