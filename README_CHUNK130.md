# Chunk 130 — Concrete PostgreSQL Runtime Adapter

Adds the concrete Psycopg 3 PostgreSQL transport to the release candidate.

- `psycopg[binary]>=3.3,<4` declared as the runtime dependency.
- `psycopg_connector()` provides the injected real connection boundary.
- `psycopg_connection_factory()` provides a repository/audit connection factory.
- Missing Psycopg is reported as a deterministic configuration/driver failure.
- No credentials are embedded in source or release artifacts.
- Live trading remains disabled; this chunk does not submit orders.

Current VPS database work remains safe to test in staging only.
