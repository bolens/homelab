# Recovery and storage review

Date: 2026-10-22. Scope: FR-019–021 and T027–030. The review covers existing uncommitted feature files in the managed worktree, including untracked files. This is a self-review, not an independent review.

| Requirement | Changed source | Verification |
| --- | --- | --- |
| FR-019 | `independent/patch_source.py`: controller credential clear and scheduled missing-token cleanup | Actual native controller clears credentials, queue remains pending, reconnection produces one confirmed mutation and no repeat |
| FR-020 | `independent/IndependentProvider.cs`: signed snapshot, origin/key binding, atomic private-file replacement and creation-only restoration | Fresh native process uses saved capabilities during HTTP 503 while delivery stays disabled. Changed key/origin, corruption, oversized state and valid revocation disable creation. Actual native queue creates during cold-start outage and recovers |
| FR-021 | `providers/transport.py`, `providers/sync.py`: cache quotas, receipt classification, durable reservation and SQLite page budget | Eight small-budget tests cover UTF-8 bytes, entry quotas, startup pruning, old receipts, ambiguous reservations, restart, parallel admission and refusal before external mutation |

## Findings resolved during implementation

The native controller had a second event-deletion path in addition to scheduled cleanup. Independent token clearing now preserves events and rule history, handles empty-credential provider-info locally, sends the normal UI refresh notification and returns before background scheduling. Official cleanup remains on its original branch.

New storage tables distinguish optional reconciled receipts from protected receipts and reservations. Legacy receipt rows remain unclassified and protected. The fixture reset initially omitted the new tables and caused uniqueness failures after a simulated external commit. Reset now clears all fixture state together, and the native recovery cases pass.

A protected reservation is durable before the external mutation. Failed/ambiguous delivery leaves it unconfirmed. Existing confirmed retries remain usable at capacity. Optional reconciled receipts can be pruned without becoming evidence of completion for a protected request. No key, token, review body or title is stored in reservation keys.

Snapshot restoration now uses compare-and-swap. If a concurrent valid manifest replaces the in-memory snapshot while an older file is being read, restoration keeps the newer decision instead of overwriting it. The final native gate and image rebuild include this correction.

A UI-path check also found that disconnect relies on the provider-update notification to refresh the page. The final controller calls the existing local empty-token handler before returning. The native case verifies that the account name clears and one notification is sent, alongside queue retention and reconnection.

## Evidence and limits

- Provider suite passes 143 tests, zero skips.
- Independent suite passes 17 tests with all source/assembly inputs, zero skips. This includes 13 compiled native queue/controller/wire cases and fresh-process capability snapshot tests.
- Ruff, Hadolint, whitespace checks and repository validation pass. Validation skips the generated PostHog bundle and unavailable locked Markdown lint tooling. Existing unrelated metadata/example warnings remain.
- Both images build. The final application rebuild and repeat of all 17 independent tests include the snapshot concurrency correction. The 13 native queue/controller/wire cases were repeated with the UI-notification assertion and pass.
- Stopped-volume backups restored byte-for-byte with matching ownership, modes, timestamps and attributes. SQLite integrity, isolated startup, authenticated capabilities, anonymous access refusal and EPUB reading passed. Both restored and live snapshot files passed HMAC/origin/size and mode-0600 checks.
- Live startup and native metadata search pass. Calibre retains 90 books/91 formats, all 90 exports retain their content hashes, and Kavita retains 90 indexed files. All recorded lock columns were compared by primary key across every table. Account identities, provider settings, permissions and reading state are preserved. Existing mounts, networks and ignored environment configuration are unchanged.
- Public Kavita, Calibre-Web and Readarr pass their health/access checks. The daily synchronization timer remains active. Temporary operation backup/restore copies were removed only after successful preservation checks. Previous images remain available. No updated-image rollback was required or exercised.
- No personal provider write was used for rollout acceptance.

Protected receipt retirement remains an operator reconciliation operation. At full capacity the safe behavior is to hold new protected writes. The SQLite main-database budget does not impose a filesystem quota on WAL files. Normal free-space monitoring remains necessary. Genuine provider-account writes, OAuth scopes and outstanding parity limits remain unverified.

## Review result

No remaining actionable finding was identified in this scoped follow-up after the controller, notification and snapshot concurrency corrections. Tests use simulated provider writes, a real gateway, and compiled native service/controller paths. Genuine intended-account acceptance remains open. The remaining full-feature gates are T004, T008 and T026.

## Final image identity

- Gateway configuration: `sha256:7e8496225470f7d063bf33f3d59070421d8c224a467219649eb63ec0d3c426d4`.
- Application configuration: `sha256:afbc50f6bb0a2179d121cee5401b9d553c89de1b4dc9bd7f932a993a9122ec59`.
- Final runtime source hashes match the built images. Installed Calibre synchronization helpers match this worktree. All four containers pass final health checks, and native public search returns ten matches.

## Repository delivery review — 2026-10-22

The delivery branch starts at current main after the earlier operational work. A separate self-review traces gateway authentication, fixed provider origins, redirect refusal, personal-action admission, protected receipts, snapshot recovery and the Calibre backup/restore and writer-resume paths. The current provider suite passes 143 tests, Calibre helpers pass 65 tests and all 17 independent integration tests pass, including 13 compiled native queue/controller cases. The patch check uses a fresh export of the pinned source. These are fixture results; genuine intended-account acceptance remains open.

Delivery fixes add dependency-update ownership for both Dockerfile directories, record the optional provider-state volume in metadata, preserve executable helper modes and remove trailing template whitespace. The generated catalog and Pages content are refreshed from source. Prose that triggered the credential scanner is reworded without disabling its checks. This delivery performs no live service changes.
