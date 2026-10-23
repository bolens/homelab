# Implementation Plan: Verified archive repair

**Branch**: `codex/comic-worker-decoder` | **Date**: 2026-10-08 | **Spec**: [spec.md](spec.md)

## Summary

Install bounded refusal diagnostics first, then a dedicated native-owned preparation/adoption route for one lossless ZIP directory-spelling repair. Ordinary inventory, nested metadata lineage, correction policy and import acknowledgements retain their current meaning. A diagnostic or prepared copy cannot authorize publication.

## Technical Context

- Runtime: the existing Mylar and normalizer Python images; actual selected-runtime checks include Mylar Python 3.10.
- Dependencies: existing publication guard, native Controller, existing-only shared Writer, complete correction census and native/reader transaction boundaries. No new external dependency.
- Storage: private preparation, custody and phase records inside existing application state, outside scanned media. Diagnostics add no mount; prospective plan13 replaces two temporary library/retention binds with one exact private common-root bind described in the owning contract. No automatic remote directory creation.
- Tests: disposable byte, SQLite and filesystem controls; source/image imports, native/generated parity, late-change/lost-response controls and verified scoped live acceptance.
- Limits: 128 MiB for buffered runtime diagnostics within the existing 768 MiB worker allowance, 512 MiB source for owned native repair preparation, existing 4,096-member/4 GiB expanded/per-member/metadata limits and monotonic deadlines. No remote access during classification or while Writer is held.
- Profile: one empty stored Unix directory with consistent directory flag and missing slash in a closed ZIP32 archive. Other ordinary supported variants stay on ordinary inventory.

## Constitution Check

Portable examples contain no private archive paths, identities, reader rows or credentials. Inspect Compose, environment, metadata, preparation, ingress and README together; diagnostics add no settings, mounts, privileges, ports or runtime dependencies. The dedicated plan13 NFS purpose explicitly amends transient bind admission for a private G containing only library L and retention R; permanent Compose mounts, settings, ports and privileges remain unchanged. Existing-only state and writer ordering remain mandatory. Live adoption requires measured consistent affected-state backup, independent restore, custody, actual reader/native verification and compatible rollback. Source, image and live acceptance are separate. One integration owner handles tracked files, Git, generators and live operations.

## Project Structure

Native modules: `stacks/mylar3/config/publication_archive_{layout,derivative,repair,diagnostics}.py` and owning tests. `publication_native.py` invokes diagnostics only after direct ordinary inventory refusal. `scripts/sync-publication-reader.py` generates exact worker copies; `stacks/komga/normalizer/publication_guard.py` preserves terminal refusal. Native installation, image verification, workflow diagnostic capability and normalizer Dockerfile change together.

Dedicated native preparation/adoption belongs in `publication_archive_owned.py`, its tests, `publication_api.py` and actual processing/reader boundaries. Reuse reviewed conversion/reader primitives only where their contracts match; never widen nested lineage or generic worker import permission.

## Design and Delivery

US1 independently delivers confined stable-source classification with fixed status/reason and terminal refusal. Valid ordinary verification skips it. Catalog, owner and admission failures cannot trigger it.

US2 captures actual source/witness, current owner/catalog/census and custody under Writer, writes an exclusive private derivative, fsyncs and independently inventories readback. Seal every source/stage/custody/ancestor fact before returning non-executable preparation.

US3 creates the dedicated same-payload repair capability only after current allowed-owner/correction and exact reader continuity checks. Exceptional original inventory applies only to the captured source; other owner archives retain ordinary verification. Durable predecessor/phase binding prevents unverified replay or acknowledgement. Native/reader acceptance precedes cleanup.

Features 022/023 complete current-library acceptance still gates general writer release. Do not recreate Mylar while claiming a process-local startup hold survives. Diagnostics or private copies alone cannot release it.


## Prospective NFS purpose implementation

The current source implements plan13/action-v3 `rename-link-v1` using actual
common-root/mountinfo joins and separately sealed original NFS facts over the
existing pipe before Writer. Each of six link/unlink transitions has intent/done
receipts; typed explicit reversal uses the original live capability. Baseline v2
and the independent verifier cover complete phase evidence and common-root
custody; legacy schemas/local exchange remain supported. The source contract
requires cooperating-writer exclusion plus absence of independent actors writing
selected names; it does not claim conditional unlink against a post-CAS actor.
See [the exact contract](contracts/archive-repair.md#prospective-nfs-renamelink-purpose).

Host controls use real local files, descriptors and SQLite with explicitly
substituted installed custody/NFS admission. The finite disposable creator, fresh bootstrap, native-data stages and explicit
plan13 role/library mapping are implemented. The optional original-session SSE
observer records bounded task-empty facts without granting quiescence or future
work exclusion. The maintained active-input assembler and exact host-engine intent
producer are implemented and independently reviewed. The historical 1,219-control,
72-suite Python 3.10 source generation passed without skips. Current combined
verification is recorded in the task and evidence files. The current configured
entry already forwards original NFS inputs, and
the birth/probe/lease/session producers are connected below it. The host engine currently refuses unbound create/start
calls. The effective-scope observer's reviewed optional bootstrap-original join derives
the disposable reader's exact original absolute NFS library mount and preserves
the separate production mapping. Source/compile controls pass. These source
contracts remain separate from actual configured observation and application
execution. Selected-image installed factories,
actual NFS and actual native/worker terminal/ACK execution remain required; this
batch does not complete T012/T015 or authorize live repair.


## Explicit disposable NFS searchability

Creator request v3 and geometry v2 `searchable-common-root-nfs` address daemon
path traversal on root-squashed NFS without changing live storage or exports.
Only the fresh supplied NFS scratch parent and newly created common G use exact
UID/GID1000 mode0711. Library/retention leaves and local state stay0700, credentials
0600. Existing ancestors must already be searchable; existing failed generations
are never chmodded or adopted. The single transient G bind, exact per-role L
mounts, two-child namespace, full9/FD custody, mount-ID and role exclusions remain
unchanged. Legacy Creator v1/v2 and geometry v1 keep their exact0700 contract.
The owning source contract documents stat-visible names and the absence of
non-owner enumeration/write rights. Component tests and a separate disposable
bind probe do not establish full Creator, NFS lifecycle, import or ACK acceptance.

## Disposable network allocation prerequisite

An exhausted Docker automatic address pool must not trigger deletion or adoption
of retained fixtures. Creator request v4 extends v3 with one explicit `network`
contract: version1, kind `explicit-disposable-ipv4`, and an operator-selected
canonical RFC1918 IPv4 `/28` subnet. Legacy v1–v3 allocation remains unchanged.
Before the sole network-create intent, read bounded current IPv4 routes from all
host tables and every current Docker network profile. Refuse malformed replies,
overlap with any non-default host route or Docker subnet, and unknown outcomes.
Create only the original nonce-labelled internal bridge with the exact subnet;
verify its returned identity and IPAM before creating containers. Recheck IPAM
when producing the Bootstrap plan. No automatic fallback, retry, existing-network
adoption, cleanup, published port or permanent Compose change is introduced.

Acceptance requires positive explicit allocation plus conflicting host/Docker
routes, malformed inputs, changed IPAM, lost replies and legacy behavior controls.
Host controls substitute the engine and do not prove actual network, NFS or
connected recovery acceptance. A fresh checked source cohort and new fixture
generation are required after delivery; preserve all refused attempts.

## Owning host reads and causal disposable repair fixture

The configured host path must explicitly bind its read-only owning-UID adapter
to original geometry v2 G/L/R. Temporarily changing effective UID is limited to
fixed, bounded filesystem reads; semantic validation, callbacks, Docker and pipe
operations run only after verified Root restoration. Root-owned local evidence
keeps its existing reader. No EACCES fallback, arbitrary callback, permission
change, mutation grant or permanent Compose privilege is introduced. Single-thread
and credential-restoration checks fail closed. The actual metadata-only owning
read passed on the original target filesystem. NFS mutation and connected
lifecycle acceptance remain required.

A separately explicit disposable repair request may derive the supported
missing-directory-slash defect from the actual imported target only inside the
original stopped-reader/Writer action. Join original bootstrap/catalog provenance
and owner-derived path before mutation. Retain a durable valid genesis, prove
all page/metadata bytes unchanged and byte-exact repair back to that genesis,
then preserve the malformed successor as the repair baseline. Rollback restores
that malformed baseline; it does not reset the fixture to its valid genesis.
Failure, uncertainty and lost replies hold without automatic reset or replay.
This test-only request does not extend the public API or accept live repair.

### Configured Parent incarnation correction

Keep the root cohort's exact installation-receipt source binding. Project its
Parent role through an explicit original-source to declared-installed-source
join, with both full signatures, fixed source hash, byte identity and final
Tree-origin closure. Use that installed copy for both child execution and child
cohort self-path. The real consumer regression must use distinct original and
installed incarnations. Preserve private/public role policy and all existing
child guards. Source controls do not complete T012 or T015.

### Admission closure and diagnosis

Deduplicate identical control metadata by exact path within each Tree check,
refusing conflicting facts before callbacks. Preserve both closure passes,
original seals and fresh validation on every call. Test duplicated file and node
mutation after namespace callbacks as well as cross-call drift.

Retain bounded, sanitized original exception-context frames, including contexts
suppressed by a wrapper. Bound examined nodes and exception depth; do not read
exception-subclass properties or emit messages, locals or raw paths. Keep
diagnostics informational. Preserve the 120-second scope/runtime limit and prove
actual configured latency with a fresh generation before claiming acceptance.
