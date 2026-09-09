#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT_DIR="${1:-${ROOT}/release-artifacts}"
mkdir -p "$OUT_DIR"
python3 -m compileall -q "$ROOT/src"
if command -v pytest >/dev/null 2>&1; then pytest -q "$ROOT/tests"
fi
ARCHIVE="$OUT_DIR/cybernetics-engine-release-candidate.tar.gz"
tar --exclude='__pycache__' --exclude='.pytest_cache' --exclude='release-artifacts' -czf "$ARCHIVE" -C "$ROOT" src deploy pyproject.toml requirements.txt sql README.md README_CHUNK122.md BUILD_STATUS_CHUNK122.md
sha256sum "$ARCHIVE" | tee "$ARCHIVE.sha256"
printf 'Release artifact: %s\n' "$ARCHIVE"
