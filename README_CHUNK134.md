# Chunk 134 — Dhan V2 Live Market Feed Protocol Layer

This chunk adds the protocol-level market-feed foundation needed before connecting the Cybernetics Trading Engine to real-time Dhan ticks.

It is deliberately separated from strategy and execution. The new code can decode Dhan's binary feed packets and can receive them through an injected async WebSocket transport, but it does not place or cancel orders and does not auto-start a live feed.

The next operational step is to deploy the package, verify the dependency boundary, and perform a tightly scoped read-only Dhan WebSocket smoke test with a small instrument set before wiring the stream into candle/state/scanner processing.
