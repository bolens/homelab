# Acceptance matrix

Every row needs executable evidence before its activation gate. First-increment unit
proof does not satisfy real-package, native, final-image or live gates.

| ID | Gate | Cases | Required evidence |
|---|---|---|---|
| R1 | Process foundation | Success, nonzero, missing binary, bad cwd, timeout, output flood, parent exits with child holding pipes | Bounded output/deadline; direct child reaped; same-group descendants stopped; sanitized repr |
| M1 | Metadata foundation | Volume 1/year, Unicode, annual/variant fields, multiple arcs, partial original/explicit pairs, mismatched counts, missing values, comma ambiguity | Explicit overrides, no fabricated identity, matched arc positions |
| M2 | Metadata foundation | Existing notes/web/CBL-adjacent XML, pages/bookmarks, unknown fields, malformed/oversize/DTD XML | No implicit loss; precise rejection; repeat reconciliation idempotent |
| C1 | Real CLI | Exact pinned runtime version, exit 1 version banner, unavailable/wrong version, malformed success output | Observe actual binary; exit/banner cannot bypass content checks |
| C2 | Real archive | Regular, annual, variant, volume 1, Unicode, multiple/new/existing arcs, notes/web/legacy comments/unknown tags | Page/member/comment hashes, exact approved XML delta, valid CRCs |
| C3 | Archive failure | Nonzero, timeout, truncated ZIP, unreadable entry, changed page, empty tag, unchanged file, symlink, low space | Original hash/permissions retained, staged data removed or recovery recorded |
| C4 | Publication | Source race, file replacement failure, crash before/after rename, restart, repeated job | Atomic ownership, durable intent, deterministic recovery, no duplicate write |
| N1 | Native | Automatic/manual, disabled tags, overwrite off/on, CBL-only and mixed preferences, alternate config root | Old/new return contracts, settings unchanged, unsupported choice explicit |
| N2 | Conversion | CBZ, CBR, CB7, CBT and conversion-only with worker enabled/disabled | Exactly one converter, retained original on failure, no second tagger converter |
| N3 | UI | Added, updated, unchanged, failed, timed out, unsupported | Accurate monitor and history at mobile/wide sizes, no raw output/secrets |
| P1 | Packaging | Final image user, runtime venv/ICU/console, architecture, dependency hashes, no Qt | Offline CLI and full native matrix in final image, legacy still available |
| L1 | Rollout | Idle drain, app/canary backup+restore, old/new read state, canary, rollback | Record/media preservation, NZBGet/Komga uptime unchanged, cleanup receipt |
| D1 | Discovery | Disabled default, missing optional package, cookies, redirect, POST, proxy, TLS verify, 429/503/timeout/reset | Same normalized outcomes and cooldown accounting, bounded cleanup, redacted diagnostics |
| D2 | Byte transfer (future option) | Unknown/zero length, 200 vs 206, wrong range, 416, compressed body, HTML, short body, bad ZIP, cancellation/restart | Same verified_transfer outcomes and preserved partials, explicit identity encoding |
| D3 | Streaming (future option) | Slow consumer, multi-GB pack, server stalls, parent cancellation, response close | Fixed buffer bound independent of body size; cancellation deadline and cleanup tested |
| D4 | Transport rollout | Switch while idle/active, rollback, provider cooldown, NZB fallback, queue priority | Choice applies at next session boundary, active work retains owner, no cooldown bypass |
