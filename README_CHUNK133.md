# Chunk 133 — Corrected Dhan Reconciliation Boundary (R2)

This release adds a conservative initial-account adoption boundary to Dhan↔PostgreSQL reconciliation.

Orders are reconciled only when Cybernetics ownership can be established through the `CTE-` correlation-id namespace or an already-linked internal broker order ID. Pre-existing/manual orders outside that namespace are ignored for engine reconciliation.

Pre-existing non-flat positions are quarantined and still block full position reconciliation until the engine has a safe internal representation of broker instrument identity.

No broker mutation is performed by this chunk.
