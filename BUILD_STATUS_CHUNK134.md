# Cybernetics Trading Engine — Chunk 134
## Dhan V2 Live Market Feed Protocol Layer

Status: BUILD COMPLETE — not deployed

### Scope
- Adds a deterministic Dhan V2 live-market-feed binary decoder for Ticker, Quote, Previous Close, OI, Status, Full, and disconnect packets.
- Adds exchange-segment mapping used by the Dhan V2 market-feed protocol.
- Adds concatenated-binary-message decoding with fail-closed length validation.
- Adds a read-only asynchronous Dhan market-feed client boundary using the existing secret-provider pattern and injected WebSocket transport.
- Keeps order placement/cancellation outside this component.
- Does not automatically connect, subscribe, or alter the running systemd service.
- Preserves current PAPER mode and disabled real order submission.

### Dhan protocol basis
The implementation follows DhanHQ V2 market-feed documentation: WebSocket endpoint `wss://api-feed.dhan.co`, access-token/clientId/authType query parameters, JSON subscription messages, little-endian binary responses, and the documented packet layouts. Dhan documents up to five market-feed WebSocket connections with up to 5000 instruments per connection and up to 100 instruments per subscription message.

### Validation
- Focused tests: 6/6 PASS
- Python compileall: PASS
- Wheel build: PASS
- Wheel SHA-256: `56593ee0582747726ba14f439996e13288a55cd272fe91591a5503cd9b021bbd`

### Safety
- No broker order API is called.
- No credentials are embedded in source.
- No live-mode enablement is included.
- Actual Dhan WebSocket connectivity is intentionally a subsequent runtime-validation step.
