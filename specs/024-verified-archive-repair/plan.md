# Implementation Plan: Verified archive repair

**Branch**: `codex/comic-worker-decoder` | **Date**: 2026-10-08 | **Spec**: [spec.md](spec.md)

## Summary

Install bounded refusal diagnostics first, then a dedicated native-owned preparation/adoption route for one lossless ZIP directory-spelling repair. Ordinary inventory, nested metadata lineage, correction policy and import acknowledgements retain their current meaning. A diagnostic or prepared copy cannot authorize publication.

The four corrective designs below are implemented and delivered through PRs
#507, #509, #510 and #511. They document the retained boundaries, not a new
implementation queue. The remaining execution order is owned by
[tasks.md](tasks.md#current-remaining-work): one isolated forward, one distinct
rollback, then separately scoped operational acceptance. Do not add another
plan, fixture generation or review layer unless a concrete uncovered failure
requires it.

Current execution is the shared isolated pair in `tasks.md`. NFS readiness and
reader stop are intermediate milestones. The stopped-reader handoff must retain
the original configured profile through its expected lifecycle transition, and
the finite retained protocol must cover that handoff without confusing session
lifetime with the separate 120-second admission-freshness requirement. Preserve
physical Writer checks, original process/FD custody and unknown-outcome holds.
Do not create another task, wrapper or review layer for each uncovered seam.

## Technical Context

- Runtime: the existing Mylar and normalizer Python images; actual selected-runtime checks include Mylar Python 3.10.
- Dependencies: existing publication guard, native Controller, existing-only shared Writer, complete correction census and native/reader transaction boundaries. No new external dependency.
- Storage: private preparation, custody and phase records inside existing application state, outside scanned media. Diagnostics add no mount; prospective plan13 replaces two temporary library/retention binds with one exact private common-root bind described in the owning contract. No automatic remote directory creation.
- Tests: disposable byte, SQLite and filesystem controls; source/image imports, native/generated parity, late-change/lost-response controls and verified scoped live acceptance.
- Limits: 128 MiB for buffered runtime diagnostics within the existing 768 MiB worker allowance, 512 MiB source for owned native repair preparation, existing 4,096-member/4 GiB expanded/per-member/metadata limits and monotonic deadlines. No remote access during classification or while Writer is held.
- Profile: one empty stored Unix directory with consistent directory flag and missing slash in a closed ZIP32 archive. Other ordinary supported variants stay on ordinary inventory.

## Delivered correction: finite owning metadata closure

The preserved U attempt passes SourceCohort but fails the effective-runtime
freshness guard before NFS-ready or reader stop. Its original runtime is 109.94
seconds old at helper start and 126.90 seconds old at exit. Both archives and
reader records/pages pass independent post-hold comparison. Keep U held; do not
retimestamp its facts or change the 120-second guard.

Before the next configured generation, implement a finite metadata vector under
the existing owning read scope. Accept only bounded immutable path/five/full9
expectations, reject exact-path conflicts before I/O, and retain local reads as
Root. Only original in-geometry caller-supplied control paths may enter the
masked UID1000 interval. The geometry checker separately retains its exact
original ancestor reads.
Every path retains its no-follow walk and fresh ancestor FD/path closure; no
callbacks or semantic validation run under UID1000. Preserve Root restoration,
primary-error retention, descriptor cleanup, poison and source/code/geometry
checks. Common G keeps full9/namespace custody and L/R keep identity5 custody.
Batch the geometry checker's admitted paths and exact ancestors separately,
retain both held-FD passes, and seal the actual primitive ledger dictionaries.
Revalidate final ledger types before conversion or equality.

Invoke a new vector independently for each existing Tree closure pass, retaining
namespace callbacks between passes and final logical seals. Capture its original
callable and dependencies from the actor's constructor seal before callbacks;
reject changed function/code bindings before the final direct invocation and
after replaceable closure callbacks. No cross-pass/cross-call metadata cache,
reusable checked flag, deleted lifetime check or new operational authority is
permitted. Require hostile-callback and restoration regressions, actual bounded
Root/NFS timing, delivery, a new checked installation and a fresh fixture before
configured acceptance. Historical source and benchmark results remain partial.

## Delivered correction: original host operation and child namespaces

V reaches the owning NFS child but holds while the UID1000 mapping validator
physically resolves an original host mount source behind the Root-owned private
operation parent. The actual child uses the separately owned projected operation
tree. Preserve V and its helper without replay. Do not make Root directories
searchable or reinterpret a permission failure as successful validation.

Before another configured attempt, distinguish the exact original plan13
operation host reference from the actual child operation destination. Keep the
original plan and source authenticated, Root host-directory custody and final
closure, exact created/started helper profile joins, and physical child-path
checks. Any exception must be finite to the original writable operation mount,
with strict primitive absolute spelling and exact host/child joins. All other
host sources retain physical canonical checks. Refuse aliases, shadowing,
foreign destinations, altered original plans and late ancestry changes.

Verify the private Root/UID1000 geometry and refusal boundaries with focused
controls and independent review. Advance host-only source pins and installation
receipts together, then use a fresh disposable fixture. No native SDK, selected
image, worker image, freshness guard or runtime permissions change follows from
this correction. Source tests alone do not close configured recovery acceptance.

## Delivered correction: owner-principal mount observation

X passes the original operation namespace check, then holds when the Root host
engine runs `findmnt` against the helper's newly created UID1000 mode0700 NFS
staging directory. A read-only comparison against that exact retained directory
succeeds as UID1000 and returns failure as Root. Preserve X and its helper
without replay; retain the private directory mode and export policy.

Run only the existing source-admitted `findmnt --json` subprocess as fixed
UID1000/GID1000 with no supplementary groups. Lower identity in the new child
process, never in the owning Python Parent and never through a Python pre-exec
callback. Keep Docker commands under their current identity, exact source-derived
argv/input/use limits, remote Writer-window guard, deadline and output bounds.
Do not accept caller-provided identity options, extra verbs, fallback mount facts
or synthetic success. Existing same-library mount/device and final original
geometry/source closure remain required.

Verify subprocess identity isolation, command and keyword refusals, unchanged
Docker dispatch, failure/timeout propagation and the actual retained NFS mount
comparison. Independently review the integrated source, update semantic pins
and installation receipts, pass delivery gates, and use a fresh installation and
fixture. This host-only correction does not complete forward or rollback
acceptance or change image inputs.

## Delivered correction: original retention-root probe binding

A bounded daemon check accepts a fresh empty mode0700 UID1000 bind source
whose parent is searchable, but refuses the nested probe directory behind
mode0700 retention ancestors with `permission denied`. Owner-principal mount
observation does not fix Docker's Root source lookup. Preserve the unconsumed
forward and rollback packets and all diagnostic originals.

For genuine plan13 common-root geometry only, bind the original retention R
at its identical canonical child path instead of binding the nested fixture.
Keep the private fixture, source and target identities unchanged. Do not make
private ancestors searchable, bind writable common G or library L, or admit an
arbitrary ancestor. Retain original geometry, held descriptors, source and
namespace closure through preparation and the first mutation.

Extend the prepared namespace proof explicitly for this exact retention bind.
The owning HostProbe must join the created mount to its original sealed mapping
and the child must independently observe the same binding before prepared ACK
and again before mutation. Preserve exact export, fsroot, device, options and
original nested root9 checks. Legacy direct-fixture and ungated behavior retain
their existing strict contracts. Refuse aliases, foreign ancestors, substituted
proofs and late row or geometry changes.

Require focused regression controls, independent integrated review, complete
source-pin closure, local and hosted delivery, and fresh checked installation
and fixture inputs. Actual forward and distinct rollback remain acceptance
requirements. This correction changes no permanent mounts or export policy.

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

The observed source-suffix NFS namespace is an explicit alternative to the
existing export-plus-fsroot representation. Both host and child fsroots must be
`/`; the child source must equal the original host export plus the exact relative
host bind subtree. Apply this relation to both probe validators and native
adoption's mountinfo join, preserving all target, identity, device, access,
same-mount and nested-mount checks. Require matching installed image/SDK evidence
for the changed native adoption module before another connected attempt.

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
connected recovery acceptance. Each attempt requires a fresh recovery packet,
operation and current role/scope bindings. An untouched original fixture may be
reused only when its original Creator sources, images, geometry, data and process
epochs still satisfy the exact joins. Changed installed controls require fresh
checked outputs. A consumed or held fixture must not be replayed or adopted as
fresh; preserve every refused attempt.

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
