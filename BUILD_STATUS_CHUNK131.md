Chunk 131 status
================
Baseline: Chunk 130
Scope: Canonical PostgreSQL runtime integration and staging installer atomic-switch correction.

Validation performed in build environment:
- compileall: PASS
- complete inherited test suite + Chunk 131 tests: 955/955 PASS
- installer shell syntax (`bash -n`): PASS
- production payload source/deployment layout: PASS
- credential literal audit: PASS (no embedded DB password/secret material)
- live broker order calls: not performed
- live trading: disabled by design

Operational VPS validation still required:
- verify the running systemd service observes the external PostgreSQL DSN
- verify runtime self-check reports `persistence_not_ready` cleared when PostgreSQL is healthy
- verify recovery/order/position reconciliation gates remain blocked until broker reconciliation is genuinely wired
- verify corrected installer keeps `/opt/cybernetics-engine/current` as the release root with no nested `current.next`
