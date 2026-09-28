# Feature specification: Modern tagging and optional DDL transport

**Branch**: `codex/mylar-modern-tagger` | **Created**: 2026-09-28
**Status**: Planned migration, first implementation increment
**Baseline**: `060b782cd1d3c970ab80fb01771ffea6f6d427d0`

## User scenarios and testing

### US1 - Tag comics without losing information (P1)

An operator can use a modern tagger while retaining pages, extras, reading order,
existing metadata, and saved preferences. This is the primary migration requirement.
**Independent test**: Generated comics round-trip through the candidate tagger with
identical page and sidecar hashes and the expected metadata.

1. Given regular issues, annuals, variants, Unicode names, and explicit volume 1,
   tagging preserves their identities and records the requested metadata.
2. Given existing notes, links, reading order, unknown metadata, and legacy tags,
   tagging preserves them unless a specific supported overwrite was requested.
3. Given multiple story arcs, each name retains its corresponding sequence number.
4. Given an unsupported write mode, the operator sees an explicit result and their
   preference and source remain unchanged.

### US2 - Recover from tagging failures (P1)

An operator can distinguish added, updated, unchanged, failed, and timed-out tags.
**Independent test**: Inject process, archive and publication failures and compare
original files and processing receipts.

1. Given a hanging tagger or version probe, the operation ends within its deadline
   plus two seconds and no child remains running.
2. Given a failure, corruption, interrupted replacement, or concurrent source change,
   the original is retained and no false successful import is recorded.
3. Given a retry or restart, the system neither repeats a confirmed replacement nor
   loses the source needed to recover an uncertain replacement.
4. Given conversion-only work, the owning converter handles it once without metadata
   writes or a competing tagger conversion.

### US3 - Choose an optional DDL transport (P2)

An operator can opt into an alternative for provider discovery without changing
archive download validation, scheduling, cooldowns, or NZB fallback.
**Independent test**: The same local server scenarios run against both choices.

1. Given no opt-in, existing downloads and saved preferences behave as before.
2. Given opt-in, redirects, cookies, proxy settings and failures have equivalent
   application outcomes and secrets do not enter logs.
3. Given an unavailable optional dependency, selection fails explicitly. There is
   no silent provider retry, transport switch, or multiplied cooldown accounting.
4. Full archive transport is a separately gated option: cancellation, resumptions,
   memory bounds and corrupt responses must match the existing download contract.

### Edge cases

Missing binaries, wrong version, noisy or malformed output, inherited child pipes,
nonzero exit, partial metadata, malformed XML, duplicate metadata fields, ambiguous
arc delimiters, unreadable archives, symlinks, insufficient disk, file races,
restart during publication, disabled tagging, manual tagging, archived annuals,
non-ZIP inputs, unknown Content-Length, redirects to HTML, invalid Content-Range,
429/503 cooldowns, TLS errors, proxies and stalled bodies.

## Requirements

- **FR-001** Preserve every page, unrelated archive member, legacy tag, unknown
  metadata field, archive comment and source permission unless explicitly changed.
- **FR-002** Preserve operator settings and issue/annual identities. Unsupported
  preferences produce a clear result, never a silent settings rewrite.
- **FR-003** Bound all child processes and output. Retain originals on failure and
  reap the direct child and stop its process-group descendants. Never include command arguments or secrets in receipts.
- **FR-004** One component owns verified file replacement. Format conversion remains
  with the configured existing converter until its explicit migration gate passes.
- **FR-005** Report observed metadata changes and failure reasons accurately. An exit
  code or success-looking message alone does not prove successful tagging.
- **FR-006** Keep the previous tagger selectable throughout the compatibility window.
  No destructive rollback or automatic second write after an uncertain failure.
- **FR-007** Make alternative DDL discovery opt-in and independently reversible.
  Preserve download validation, retry ownership, cancellation and provider cooldowns.
- **FR-008** Verify dependencies and final images in isolation before activation.
  Use fixtures, not live comics, for acceptance tests.

### Key entities

Tag request, process result, metadata policy, verified file receipt, transport
selection and transfer outcome. Technical schemas are in [data-model.md](data-model.md).

## Success criteria

- **SC-001** Every acceptance case in [acceptance.md](acceptance.md) passes before its
  activation gate, with no skipped required preservation or rollback cases.
- **SC-002** Fixture pages and unrelated members remain byte-identical in all accepted
  operations. Every rejected operation leaves the original byte-identical.
- **SC-003** Failed and timed-out operations never appear as successful imports.
- **SC-004** Both optional capabilities can be disabled independently without losing
  preferences, metadata, queued work or receipts.

## Assumptions

Initial implementation is an isolated compatibility foundation. The legacy tagger
and requests transport remain active until their acceptance gates pass. Full-library
retagging, a general Python upgrade and new providers are outside this feature.
