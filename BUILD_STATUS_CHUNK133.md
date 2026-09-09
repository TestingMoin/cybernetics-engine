# BUILD STATUS — CHUNK 133 (CORRECTED R2)

Scope: Dhan read-only reconciliation with initial account-adoption boundary.

Corrections from the first build:
- Pre-existing/manual Dhan orders are not treated as unexpected engine orders unless they are explicitly Cybernetics-owned through the `CTE-` correlation-id namespace.
- Cybernetics-owned orders with missing internal ledger rows remain CRITICAL.
- Pre-existing non-flat Dhan positions are quarantined as `PREEXISTING_BROKER_POSITION` and remain blocked because the current internal position schema lacks exchange segment/security ID.
- Flat/unrelated pre-existing broker state does not create false reconciliation failures.

Validation:
- Python compileall: PASS
- Focused reconciliation tests: 12/12 PASS
- Wheel build: PASS
- No Dhan mutation endpoints introduced
- No live authorization introduced
- Paper/order-submission safety unchanged

CHUNK 133 R2.1 corrective patch:
- Fixed duplicate Dhan position rows so rows[0] can no longer hide a non-zero duplicate.
- Same-identity duplicate rows now select the non-zero row when present.
- Conflicting non-zero duplicate quantities fail closed.
- No broker mutations.
