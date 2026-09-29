# Research

Base: `d8634e3b4d88e934af83cdbdfd3bc2426ff3fc18`.

- Decision: cache only validated volume data, never issue data. The current worker fetches both issue and volume every time and waits the configured interval before each request. Same-series batches can avoid repeated volume requests without losing fresh issue ownership checks. A durable cache was rejected to avoid migration and secret-retention work.
- Decision: keep the original deadline in the worker payload. Parent-only expiry could lapse during issue lookup; cache hits must not renew freshness. Values are copied through bounded JSON, and context keys hash credentials rather than retain them in cache keys.
- Decision: preserve existing metadata before staging, but after durable intent. The 64 MiB offline fixture takes roughly 0.33 seconds for unchanged publication and still copies the archive. Retain snapshot, hash, attribute, recovery and handoff checks rather than optimize by weakening them.
- Rejected for this pass: reusing archive verification across publication boundaries, parallel writers, reducing provider pacing, or caching issue metadata. Those change stronger correctness assumptions.
