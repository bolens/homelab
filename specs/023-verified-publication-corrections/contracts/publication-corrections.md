# Publication correction contract v1

## Payload identity

A trusted bounded offline archive inventory verifies every member. Canonical token input is exactly `{"version":1,"members":[[name,bytes,sha256],...],"pages":[name,...]}` serialized as UTF-8 with insertion order shown, `ensure_ascii=False` and compact separators. Sort regular member rows by exact UTF-8 name bytes; do not normalize Unicode or case. Validate that the archive reader returns that exact canonical safe spelling without traversal, redundant separators, leading `./` or backslashes. Page names use the pinned tool’s natural filename ordering (ASCII digit groups numerically, casefolded text, exact-name tie-break); the complete ordered page-name list participates in the token. Thus archive header iteration order and compression do not alter identity; actual writers separately preserve their reader ordering. Exclude only exact root `ComicInfo.xml` and root `ComicBookInfo.json`; case-variant or multiple competing metadata entries are unavailable/review, not discarded. Bound root metadata to 262,144 bytes and validate its supported syntax; include all other sidecars and nested provenance. Record zero-byte directories for audit/preservation while excluding them from the cross-format token. Reject duplicate/unsafe/link/encrypted/nonempty-directory/ambiguous metadata entries, limits, instability and unsupported verification. Exact internal-name changes need a reviewed derivative alias; no perceptual identity inference.

## Native authority

Exact owners use `table`, `issueid`, `parentcomicid` and `releasecomicid`; identifiers follow the native positive ASCII decimal convention (1–16 digits, no leading zero). Regular releases require parent/release equality; annual releases retain their separate release volume. The combined explicit allowed/rejected owner count is at most eight.

Primary-key-only versioned operational endpoints prepare/commit reviewed registration and check candidate payload/owner. Restricted keys cannot register or waive corrections. Prepare binds an explicit attestation and exact current correct-owner/archive facts; commit accepts only its immutable token at the expected census revision under shared writer exclusion. Native does not treat caller metadata/hashes as proof. Historical facts outside native access require explicit authenticated reviewed attestation from a separately verified importer. No new mount or automatic worker-JSON trust is introduced.

Guard-check response includes protocol, registry epoch/revision/census, exact candidate/source binding when natively visible, proposed owner, decision and the complete immutable matched-owner facts needed for local revalidation. Path reads are confined to explicitly configured library/cache/media roots. An advisory digest-only worker request cannot authorize native import. Do not expose private manifests, arbitrary filesystem reads or secrets.

## Initialization, commit and recovery

An existing writer directory with both marker and census absent is uninitialized, never automatically accepted as an empty registry. Explicit authenticated initialization accepts a reviewed bootstrap intent binding the existing writer identity, current workflow state and verified backup/restore attestation (or an explicit reviewed fresh-install intent). Bind the existing database and writer root/lock identities, the workflow schema, and a versioned complete semantic record census. Workflow projection v1 includes every kind/key and complete decoded value except `observation`, `meta.library_seen` and `publication_intent`; it excludes the `records.updated` envelope and the separate volatile events table. Unknown kinds and all correction attestations/census remain protected. A physical workflow hash is backup provenance, not the mutable prepare/commit equality test. Protected record additions, removals or nested value changes stale the review. Allocate an immutable epoch once. The application may expose authenticated bootstrap/status routes while uninitialized, but it admits no media mutation or pending-journal replay. Fresh portable installations follow the documented one-time initialization; an initialized empty registry then preserves ordinary behavior.

All initialization and registration writes run under the existing writer lock. Persist an owned mode-0600 prepared marker with exact epoch, old/new revision/census and immutable accepted-intent digest, fsync it and its directory, atomically commit attestation/index/census in SQLite, then atomically publish/fsync the final marker. The prepared marker blocks unrelated admission. SQLite does not atomically commit the filesystem marker.

Recovery validates the prepared marker/intent and complete SQLite state. Only exact old or new census is permitted: a complete new census reconciles its final marker; an exact old census may finish the already accepted registration only after fresh admission facts pass, or record an explicit abort while retaining the immutable intent and restore the old complete marker. It cannot create a different registration. Missing/partial/mixed/foreign state holds until authenticated recovery; no automatic empty bootstrap. A final marker must match the entire census, epoch and every required attestation. Read-only authority checks require the existing owned, mode-0600, singly linked rollback-journal database and marker, with no WAL/SHM/journal sidecars. Unsupported journal state is held; checks must never create a missing SQLite sidecar or ignore an existing WAL. They acquire the workflow lock after the caller’s writer lock. Cover crashes before/after each durability boundary, marker/DB mismatch, old DB/new marker and partial record loss.

Restoring both a matching old database and old marker is indistinguishable from a coherent historical rollback by local comparison alone. Such restore requires independently verified backup/epoch/census evidence and explicit operator reconciliation; this feature does not promise universal rollback detection without an independent anchor. Preserve prior epoch/admission evidence outside the mutable pair.

## Admission and replay

Check before scripts/tagging/duplicate removal/placement/status mutation and before manual metadata/naming/rescan ownership changes. Recheck source/proof before final mutation; scripts invalidate stale stamps. Cover ordinary, annual, storyarc, oneoff, disabled/legacy tagging and converted paths. Registered payload requires an explicitly allowed exact owner and current matching correct publication; missing/stale evidence holds it. Unknown payload follows existing eligibility, never a broad issue/provider blacklist.

When the complete validated registry is empty, existing eligibility may continue without a payload scan. When it is nonempty, any unsupported or incomplete candidate inventory is unavailable and held: the implementation cannot assume an unreadable candidate is unknown. Native and worker keep rejected/uncertain sources and historical receipts. A terminal retained-review result cannot fall through to tag-failure import or failure/search replay. Every interrupted journal retains correction token, epoch/revision, candidate before/after binding and exact owner facts. Replay revalidates the latest complete census and current matched correct-owner evidence before any mutation or fence clearance; a changed registry may retain an older prepared job for review. No deletion or fence clearance follows rewritten metadata alone.

## Lock order and worker behavior

Remote advisory checks occur before the worker holds the shared writer. Under writer exclusion, validate the full census and marker through the existing read-only native config/writer mounts, require the same epoch/revision and stable candidate content, and freshly revalidate every matched correct owner’s complete all-row/deleted/annual-shadow path binding and current correct-archive payload. Either compute those facts locally or locally revalidate complete immutable advisory facts; revision equality alone is insufficient. This is mandatory for existing-target confirmations, Extras, cleanup and conversion publication that may never reach native final import. Test intervening correct-owner/path/content changes with an unchanged registry revision. Native final import repeats content/owner checks. Protocol mismatch or uncertain state holds publication. Worker never writes native registry SQLite. Cover common import submission, guided/pack routes, existing-target confirmation, Extras placement, duplicate cleanup, conversion publication and naming/metadata passes.

## Rollout

Deploy matching native first and worker second with writers held and independently restore-verified affected state. Seed only exact reviewed correction evidence. Prove conflict canary and legitimate different-payload canary, then scoped existing-repeat repair and fresh protected whole-library acceptance. Source publication and healthy containers alone do not complete live acceptance.

## Reviewed repeat retention

The primary-key POST `commitRetainedRepeat` route accepts a private exact plan
path and digest, independently verified backup/restore evidence, the complete
current census, and `repair=retain-and-clear-exact-false-location`. Prepare a new
plan against the current census after registration; do not refresh an old proof.
Native admission independently proves the registered wrong owner, every matched
correct publication, complete catalog and exact source. Its typed live owner
retains the wrong archive outside scanned roots before unlinking its exact
incarnation and conditionally clearing only the false `Location`.

`retainedRepeatStatus` validates terminal retention without repeating mutation.
It preserves `Status`, `ComicSize`, wanted intent and correct-publication bytes.
The result remains `requires_review=true`: acquisition or failed-release
provenance is not reconstructed from comic metadata. Restoring wanted state
requires separate actual history or explicit reviewed operator policy. Missing,
changed or uncertain source, catalog, census, backup or receipt retains a hold.

## Explicit reviewed nested derivative

Read-only lineage preparation binds the current correct source, complete member
and page inventories, exact nested `ComicInfo.xml` to adjacent
`SourceMetadata.xml` mapping, reviewed private preparation, retained original
and independent restore, catalog and complete current census. Rootless archives
may add only the deterministically promoted root `ComicInfo.xml`; existing root
metadata is merged without losing nested provenance. Unrelated member bytes,
headers, order, pages and archive comment remain preserved.

Authenticated `publicationControl` action `prepare-lineage` accepts the exact
reviewed lineage request and returns its immutable plan under native writer
exclusion without adopting it or changing media. Preparation is confined to the
configured private cache stage. Actions `prepare-derivative`,
`adopt-derivative` and `recover-derivative` use the existing durable registration
protocol. Adoption precedes media mutation, publishes an exact version-2
attestation, binds the full reviewed census to its immutable predecessor, and
inherits every allowed/rejected owner from all prior family relations. A
relation cannot join preexisting families or create a cycle. Unknown originals
allow only the reviewed current owner. Both original and derivative payloads
remain protected. Matching native and worker readers independently verify these
relations; fresh current owners may contain either reviewed variant.

The separate primary-key POST `commitReviewedDerivative` route accepts only the
exact committed adoption token. Its typed live native owner uses confined
private preparation, proves current source/catalog/census again, publishes the
reviewed archive and conditionally updates size while preserving status and
ownership. `reviewedDerivativeStatus` validates the immutable completed witness
without repeating publication. Uncertain intents hold ordinary startup and
worker admission even if a fence is missing. Automatic nested discovery and
direct SDK repair cannot manufacture adoption or consume arbitrary aliases.
Retained originals are not retired by this route; conclusive cleanup requires
separate acceptance.

## Bootstrap source implementation boundary

The current bootstrap helpers serialize raw writer → workflow lock → existing
SQLite transactions without ordinary native media replay. Typed immutable
bootstrap plans have bounded acceptance/outcome envelopes; explicit accepted
intent tokens bind the complete reviewed workflow/schema, physical database
and writer identities, retained pending fences and backup/restore attestations.
An aborted receipt stays terminal. A final marker requires its unchanged
prepared predecessor and a unique committed initialization witness. Neither a
missing marker nor a lost census is reconstructed as an empty registry.

Actual process-exit controls exercise all durability boundaries. Recovery can
reconcile supported prepared-old/prepared-new bootstrap states when SQLite has
no sidecars. A process exit during an uncommitted SQLite write leaves a rollback
journal; ordinary checks refuse it without changing either file. Explicit
`JournalRecovery` preparation captures retained private originals, independently
restores a copy through SQLite and binds the complete restored SQL contents,
including volatile event rows and update envelopes. It revalidates exact nested
evidence, retained copies and restored integrity/contents before acceptance or
original SQLite access. Exact plan acceptance permits SQLite to recover the
original inode, followed by complete equality verification. Interrupted changed
pairs require a new reviewed plan linked to the prior accepted plan and the same
independent restoration. SQLite consumes journals through its transaction
protocol. The helpers retain media fences and replay no media operations. A
pending recovery marker holds ordinary bootstrap calls.

Primary-key authentication, production registration integration, native installation and
startup/publication integration remain pending. Existing `Store` startup is not
yet gated against automatic SQLite recovery. This implementation boundary does
not weaken the full feature's recovery and acceptance requirements or complete
T003.

## Registration witness source implementation boundary

Read-only census validation understands exact typed registration receipts. The
immutable plan contains `version`, `action=register`, `old`, `binding` and `body`.
The attestation body excludes its intent token. Hash the plan, insert that token
into the body, hash the resulting attestation, then derive the next census. This
ordering avoids a circular digest dependency. A plan cannot embed its next
census or the materialized attestation key.

Every stored attestation requires exactly one matching committed registration
receipt. Every committed registration receipt requires its exact attestation.
Validate the entire old-census chain from the initialized empty epoch to the
stored final census. Accepted unfinished receipts hold ordinary admission even
when the marker remains final. Prepared and aborted receipts provide no
attestation authority. Committed registration receipts must match the original
database/writer identities and workflow schema, alongside the unique committed
bootstrap witness.

The complete namespace is bounded to 512 attestations, 128 bootstrap receipts,
640 registration receipts and one census. Bootstrap receipts retain their
65,536-byte limit. Registration receipts allow up to 4 MiB each. The aggregate
namespace limit remains 32 MiB. Exhaustion holds without truncation or pruning.
Fixtures cover the complete 512-attestation chain, absent/orphan/rewritten
receipts, unfinished acceptance, foreign committed bindings and malformed plans.
Production fresh native all-row owner/archive observations, authentication and
startup/media enforcement remain pending. These passive
checks alone do not establish current owner validity or prevent live imports.

## Registration transaction source implementation boundary

Internal `RegistrationState` methods prepare a bounded immutable request,
explicitly accept its exact token, publish the prepared marker, commit the
attestation/census/receipt together, and publish the final marker. They preserve
the original initialization witness and retain prior receipts. A committed replay
validates the latest complete authority and returns its original derived result.
Aborted tokens cannot register again.

Preparation and an uncommitted registration require a trusted observation
callback. It runs under the raw writer before the workflow lock and returns the
complete current inventory and correct-owner observations. Separate copies of
the reviewed body prevent callback mutation from changing the accepted request.
Both returned fields must match the reviewed values exactly. Callback equality
is an internal contract, not API authentication or a production native observer.
The adapter must independently read confined archives and the complete native
owner catalog. Those adapter controls remain pending.

Exact accepted-old recovery handles an interruption before prepared-marker
publication. Prepared-old recovery can commit only with fresh matching
observations and unchanged protected workflow/fence bindings, or explicitly
abort without publishing an attestation. Prepared-new recovery requires the
complete committed chain before finalization. A missing, foreign or mixed marker
is held. Interrupted aborts finish their old final marker without resurrecting
the token. The ordinary census check always holds accepted unfinished receipts.
Only internal exact recovery may validate its own accepted receipt as pending.

Process exits cover all seven registration write boundaries. Ordinary checks
hold a registration SQLite journal without original database/journal changes.
Explicit `RegistrationJournalRecovery` now supplies its independent recovery
protocol. Authentication, the native observer and startup/publication integration
remain required before live use.

## Registration journal source implementation boundary

`RegistrationJournalRecovery` uses the shared capture/restore/acceptance mechanics
with exact `action=registration-journal` and `registration_token` receipt fields.
The bootstrap route retains `action=bootstrap-journal` and `bootstrap_token`.
Each route refuses the other type. Registration restoration verifies the exact
accepted old intent, complete predecessor census/attestation/receipt chain and
original initialization witness before original SQLite access. The original
filesystem identities, schema, protected workflow and pending fences must match
the reviewed registration. The prepared marker must bind that old census and
the exact derived new census.

The helper restores only the complete accepted predecessor, including every
record envelope and event. It preserves the original database inode and media
fences, retains independent proof, and permits no registration or media replay.
A separate registration recovery call must freshly observe current facts to
commit or explicitly abort. A changed interrupted rollback pair requires a new
linked review proving the same complete independently restored contents.

All authority-marker and recovery-receipt predecessor comparisons use canonical
JSON equality. Boolean or floating-point values cannot alias integer protocol
versions or identities. Controls cover genuine hot journals with an existing
correction chain, seven recovery exits, interruption inside rollback, type-route
separation, retained restore tampering and coherently rehashed missing prior
records. Malformed boolean/float markers are refused before original files
change across registration and both journal routes. No live recovery, native
observer, API authentication or startup/publication integration is claimed.

### Existing-only connection and passive status foundations

The internal `Store(existing_only=True)` mode preserves the existing private
rollback-journal database. It runs no creation, permission change or schema DDL.
Every connection checks the original inode, unchanged schema and absence of all
journal/WAL/SHM sidecars, including dangling links, before normal SQLite access.
The original inode must still match after opening and after the operation. A
cached Store cannot silently recreate a lost database. This mode is not complete
authority admission or exclusion against an uncoordinated filesystem adversary;
the native adapter must acquire raw Writer before workflow LOCK. Default Store
callers retain existing behavior until that adapter is installed.

The internal `authority_status` probe acquires existing raw Writer before the
read-only complete final-authority snapshot. It never constructs Store, creates
state, initializes authority, recovers journals or replays media. Every call
revalidates current authority. Pending media fences produce a held result and
remain intact. Failures use fixed reason codes without exception text or private
paths. Writer acquisition uses zero timeout; workflow LOCK and the complete
snapshot can still wait. The result is advisory, never a cached permission to
publish. Native startup gating, authenticated API routes and production helper
installation remain required before this foundation changes live behavior.

### Internal fresh native owner observation

`observe_owners` requires caller-owned raw Writer before touching the catalog.
The database and at most eight existing library roots come from trusted native
configuration, never API filesystem parameters. The database must be an existing
owned, singly linked regular rollback-journal file under the same configured
data parent as Writer, with no journal/WAL/SHM sidecars. It is opened immutable
and read-only, checked for readability and read in one transaction. All comics,
issues and annuals participate without status/deletion filters or pagination.
The combined projections are bounded to 100,000 rows and 64 MiB; the database
input is bounded to 256 MiB.

Every nonempty path claim requires exactly one parent and a configured-root
confined path. Missing or duplicate parents, unconfined claims and malformed
values hold rather than hide potential owners. A selected IssueID must occur
exactly once across both issue tables, including deleted/locationless annual
shadows. Parent and annual release IDs must match exactly. Paused parent series
can retain a valid publication; selected issue status must be Downloaded or
Archived and annual deletion must be null or integer zero.

Lexical path checks alone cannot exclude aliases. Every claimed path and parent
receives cached metadata-only identity checks. Symlink components hold; physical
inode claims must also be unique. An uncatalogued private backup hardlink does
not create another owner. Metadata identities are reread after selected archive
verification. Path depth is at most 64 components, with at most 200,000 distinct
metadata identities and 64 MiB of identity-path bytes. Single-parent validation
precedes expansion, avoiding quadratic duplicate-parent growth. SQL, Python
projection/metadata loops and selected archive inventories share the existing
180-second cooperative deadline.

Only selected exact correct-owner archives receive complete payload inventories
and full source hashes. All allowed owners must have the same publication payload.
Current catalog facts use the strict versioned shape in the data model. Native
database/source signatures and all claim identities must remain unchanged after
verification. No library tree walk, unselected archive payload read, schema
write, automatic recovery, media mutation or initialization occurs. The internal
observer is not API authentication or publication admission. Production API
wiring, startup exclusion and all native/worker boundaries remain required.

## Authenticated protocol implementation

The checked native adapter installs `publicationControl` after all writer,
workflow and naming helper installers. It requires enabled API configuration,
the configured 32-character primary key, native normal-key classification, POST
and exactly one `request` argument. SSE keys, disabled APIs, GET, JSONP and
unknown arguments are denied before importing the controller or accessing state.

The request is a JSON object with exact integer `version: 1` and `action`.
It is limited to 4 MiB UTF-8, 16 nesting levels, 65,536 nodes and 20-character
integer literals; duplicate keys, floats and nonfinite values are refused.
Unknown fields and caller filesystem locations are refused before constructing
state. Tokens, epochs and payload IDs are lowercase SHA-256 hex strings.

| Action | Additional required request fields |
|---|---|
| `status` | None; optional exact `token` for an intent summary |
| `prepare-bootstrap` | `epoch`, `backup` with manifest/restore SHA-256 and description of at most 1,024 UTF-8 bytes |
| `initialize-bootstrap` | Exact prepared `token` |
| `recover-bootstrap` | Exact `token`, `mode` of `finish` or `abort` |
| `prepare-registration` | Complete reviewed `census`, historical `inventory`, explicit `allowed`/`rejected` owners, reviewed `evidence`, integer `created` |
| `register` | Exact prepared `token` |
| `recover-registration` | Exact accepted `token`, `mode` of `finish` or `abort` |
| `prepare-journal` | `kind` of `bootstrap` or `registration`, accepted intent `token`; optional exact `parent_token` for interrupted recovery |
| `recover-journal` | Same typed `kind`, exact prepared recovery `token` |
| `prepare-tagging-completion` | `backup` with reviewed manifest/restore SHA-256 and description of at most 1,024 UTF-8 bytes |
| `complete-tagging` | Exact prepared completion `token` |
| `check` | Exact proposed `owner`, advisory `payload` digest |

The native configuration supplies data paths and the destination library root.
Tagging completion accepts only an interrupted job with an exact immutable
terminal witness and matching receipt, archive, attributes, staging, owner and
complete current correction authority. It never runs a producer or changes media.
A private accepted ledger and pending hold span fence and intent removal;
interrupted clearance requires the same exact token and fresh unchanged facts.
Earlier or unwitnessed phases stay held for review. Responses expose job token,
ledger phase and backup hashes, without private paths or backup descriptions.
Preparation compares the complete reviewed census, observes actual allowed
owners and requires their current payload to match the reviewed historical
inventory. The SDK reobserves before preparing and before commit/recovery.
Prepare responses include exact token, immutable binding, census, owner tuples,
payload, counts, evidence digest and current archive hashes. Status reads exact
receipts through existing immutable read-only SQLite under raw Writer before
workflow LOCK; it never creates state, opens a write transaction or replays media.
Response outcomes come from durable receipts, including abort/replay. Private
manifest member names, descriptions and recovery directory locations are omitted.

Advisory checks validate the complete authority and retain pending fences. Known
payload checks freshly observe all distinct allowed owners, include current and
historical matched owner facts and hold any unallowed owner or stale evidence.
Unknown digests receive advisory `unknown` without archive reads. These responses
cannot authorize final native publication. The startup adapter enables existing-only
admission before native database maintenance and holds ordinary web/API requests,
notifications, schedules and ticks when authority or recovery is unavailable.
Health and authenticated review remain passive. Authority acceptance alone does not
release media work: successful native initialization after restart is required.
Local worker revalidation and every media mutation boundary remain unfinished work.

### Worker read-only evidence foundation

The independent worker build context includes only an explicit selection of native
read-side definitions, generated by `scripts/sync-publication-reader.py`. Repository
validation rejects stale generated copies. Registry transactions, initialization,
registration and journal recovery classes are excluded. The worker adapter changes
the trusted filesystem projection and passes one cooperative artifact-verification
deadline through the read operations: native catalog paths map to explicitly
configured, nonoverlapping worker media roots; the separate existing config and
writable writer mounts must prove the same physical writer identity. No native
mount paths are created, and ambiguous mappings hold.

Under caller-owned raw Writer, `Authority.check` validates the entire current
marker/census/witness chain, inventories the real candidate, freshly scans complete
catalog projections and inventories all matched correct-owner archives. It then
rechecks full authority and source signature/hash. Optional native advisory facts
must equal the fresh local result, including observed owner/path/archive facts;
unchanged revision alone is insufficient. Pending native tagging intents hold even
when their fence is absent. Worker recovery may use its existing owned normalizer
fence, but cannot bypass native recovery. This adapter performs no remote calls,
authority writes or journal recovery. Returned evidence cannot be cached as
permission: each final mutation still needs fresh enforcement.

The coordinated `writer_cycle` now binds this local authority before recovery
identity/fence writes and rechecks the complete namespace before fence clearance.
It requires explicit `publication_roots` mappings in private configuration.
Uninitialized/missing authority or mapping holds; there is no marker-based fallback
to an empty registry. Thread-owned scope gives subsequent mutation callers the
exact current adapter only while their shared Writer is held.

Native Mylar HTTP is refused before credential/config access when that thread owns
the writer. A zero-time physical lock probe also covers separate local registries
for the same flock inode, and releases before HTTP. This probe reads existing state,
creates no protocol files and never clears or replays any fence. It cannot authorize
publication or waive native final checks. Per-source mutation callers and durable
remote command handoffs pass source and actual-image acceptance. The worker stays
held through reviewed delivery, matching rollout and live acceptance. Complete-cycle missing/changed-authority
and physical-lock refusal controls supplement the independent portable vectors.

`prepare-fresh` accepts only protocol version, action, epoch and the same exact
backup evidence fields as `prepare-bootstrap`. It is explicit creation for a virgin
owned root under early startup exclusion. It refuses any existing native/workflow
database, SQLite sidecar, writer directory or fresh claim. An exclusive private claim
and created partial state remain retained on failure. No fallback infers a new epoch
from state loss. Status can discover the exact prepared fresh token without creating
state. `initialize-bootstrap` requires exact acceptance before authority is ready.
The first native catalog creation consumes this exact committed fresh permission
before native `dbcheck`. Existing installation startup requires an owned regular,
readable native catalog with no pending sidecars. Missing or invalid native catalogs
stay held without recreation, maintenance or worker startup.

### Worker import and maintenance boundaries

The local adapter resolves the proposed native owner from the exact read-only
`publication_native.owner` definition: unfiltered cross-table identity, annual
release ID, bounded immutable catalog reads, stable signatures and no journal/WAL
uncertainty. Proposed issue and parent IDs must be explicit strings; missing or
coerced parents cannot disable validation. It checks the complete current census
and source against that owner, then repeats owner and authority validation.

Common import submission checks before creating a stage or receipt, after copying
both original and stage, and immediately before saving its attempted submission.
Guided submission binds the exact native command, source token, proposal version
and selected issue/parent to native queue admission. The queue owns the
claimed/submitted transition. Pack member confirmation checks
both candidate and existing target before replacing verification facts. Even an
unregistered target requires fresh all-row evidence that it remains this exact
owner's unique Downloaded/Archived catalog archive; an old hash alone cannot
authorize an unbound path or changed status. Pack
cleanup rechecks every confirmed comic before writing cleanup intent, reporting or
deleting any original; old supplement cleanup stays held until its derivative
ownership contract is reviewed. On failed copy validation only the newly created,
unsubmitted copy is removed, preserving its original and prior receipts.

Coordinated import receipts bind original/staged bytes, exact owner, current
census and optional guided command before dispatch. Native independently checks
the actual shared stage before recording an attempt and again before processing.
A prepared receipt may reconstruct a lost local guided command record after fresh
source/stage validation. An uncertain attempted submission cannot be replayed.

`maintenance_handoff` version 1 accepts `packCatalog`, `packReport`,
`workflowAcknowledge` and `reportImportProblems`. The last command additionally
requires the separately advertised integer `maintenance_reports` version 1. Its strict envelope contains version, token, command,
arguments digest, complete census and at most 4,000 source observations. Each
observation names a confined native path, prepared SHA-256, optional exact
issue/parent and a boolean current-catalog confirmation requirement. Boolean
protocol versions are invalid. Authenticated health advertises this capability
separately from `guided_handoff` and `publication_handoff`.

The worker prepares private requests under Writer, durably records dispatching
before releasing Writer for HTTP, then accepts a result only after the same full
local proof is revalidated. Native checks actual archive evidence, source bytes,
complete census, current catalog binding and any guided command choice before
recording its at-most-once maintenance attempt. Native catalog drift invalidates
admission. Attempt records grant no correction authority. Lost responses retain
sources and history for review without automatic replay, including after source
or census changes. Old protocols retain prepared work.

Pack catalog evidence must agree with the actual shared archive's metadata and
filename. Reports require actual shared destinations, matching hashes and exact
current catalog owners for confirmed issues. Receipt-owned extracted originals
remain private local witnesses and must match their shared destination's payload.
A delayed report cannot erase members, replace verified phase/kind/owner/path/hash,
or clear completed inventory and cleanup. Cleanup waits for the native report's
durable exact acknowledgement, then rechecks all originals and destinations.

Extras placement rejects registered payloads and protected catalog paths or
physical aliases before metadata or placement changes. It preserves member bytes,
creates temporary archives exclusively, and rechecks source/target proof before
recording preservation. Registered-owner confirmation requires the attested
archive payload until a reviewed derivative lineage exists. Historical supplement
cleanup for unbound legacy receipts remains held; reviewed delivery and complete
live acceptance remain required. No retained proof grants replay or
HTTP under Writer. The live worker stays held until feature acceptance.


### Worker duplicate and reader boundaries

Coordinated duplicate cleanup resolves the actual target's unique current native
catalog owner, checks both archives against that owner and the full correction
census, and observes every catalog path and physical archive claim before removing
a download. Registered and unregistered current originals, including deleted or
inactive claims and physical aliases, remain protected. Page equality or a reader
READY state alone never grants cleanup.

Before unlink, retain the exact exclusive private original and bind every receipt
fact except its finite phase to an immutable digest. Existing receipts cannot be
refreshed into new permission. Recheck source/target/catalog/census, retained copy
and receipt predecessor before deletion. A lost deletion acknowledgement can
advance only with the missing original name, unchanged exact retained bytes and
fresh identical owner/target/census proof. Legacy unbound receipts stay held.
Corrupt archives cannot supply complete inventory and need reviewed owned
quarantine evidence before coordinated deletion or retry reporting.

Reader scan, analyze and metadata-refresh notifications use private typed CAS
receipts. Preparation observes exact current source/target/owner/census under
Writer; dispatch records uncertainty before HTTP outside Writer and repeats those
facts and the reader route after acknowledgement. New pending native tagging,
repair or worker publication work revokes a prepared or in-flight notification.
Native paths map through trusted roots before comparison. Lost replies are
retained without automatic replay, and a scan acknowledgement does not confirm
publication. Current-owned lossless conversion without an existing reader book uses exact native relocation and unchanged full inventories. Reader-owned originals, PDF derivatives, changed member names and legacy recovery jobs remain held until their separate continuity/derivative contracts exist.

### Owned rename, root metadata and maintenance reports

Native release naming now captures an exact owned source, immutable job facts,
current catalog owner and complete correction census before any link, catalog
update or source retirement. The archive bytes stay unchanged. Every checkpoint
revalidates those facts and the captured fence. Terminal history must be durable
before clearance; interrupted jobs remain held rather than replaying a move.
Standalone or historical naming intents cannot acquire this capability.

Preserved root ComicInfo supplementation uses an exact native producer bound to
the source, two private distinct verified copies, metadata and current owner.
Only root metadata may change; page payload, member names and catalog ownership
must survive. The producer returns a verified publication receipt. The combined native route binds an immutable private preparation to those copies, exact rename history and the worker's unchanged-hash reader restoration before metadata admission. Lost metadata responses reconcile the closed tagging witness, never the old rename hash. Nested metadata repair and member-name derivatives still require their own reviewed transitions.

Maintenance reports use the typed handoff after writer release. Their exact
versioned binding includes report, processing, guidance and an integer observation
time in a five-minute bucket, valid for at most fifteen minutes. Native admission
precedes diagnostic, guidance or import state writes. Import readiness and guided
proposals require fresh actual source and catalog evidence. Private source paths
are removed from public report arguments. Caller statuses cannot claim completed
imports or conversions. Uncertain guided attempts are retained across later
observation buckets without repeating their proposal. Old native capabilities
leave reports prepared; bounded request selection prevents a stale request from
starving an independently valid request.


### Private correction-plan preparation

`scripts/prepare-publication-corrections.py` reads explicitly reviewed private scope and review JSON and writes a private, exclusive plan. It does not call Mylar or execute registration, repeat relocation, catalog repair or cleanup. Supply `--scope-file`, `--review-file` and `--output`; the output parent must already be a private directory. Diagnostics contain only readiness and a plan digest.

The version-1 scope contains `config_dir`, `library_roots` and `tool_root`. The reviewed document contains the exact complete `census`, explicit `allowed` and `rejected` owners, `correct` owner/path/SHA-256 observations, optional `repeat`, private `evidence` and `backup`, and integer `created`. Backup proof names a manifest and independent restore receipt with their SHA-256 values. The manifest binds source/backup/restore files for each required role; copies must be physically distinct, outside the library, intact and database-readable. Current native catalog, complete census, actual archives, private evidence and backup files are reread under existing writer exclusion. No acquisition or failed-release provenance is inferred.

The resulting `registration_request` uses the existing `prepare-registration` protocol. A later register operation requires the exact token returned by native preparation. Every plan remains `executable=false`. Optional repeat observations carry `fresh-native-retention-review-required`; they authorize no source retirement or catalog changes.

Ordinary startup and advisory admission also hold unfinished or malformed private
conversion and retained-repeat records when a crash preceded their filesystem
intent. Passive terminal ledger validation cannot reconstruct a publication
capability. Combined-publication phases waiting for reader restoration retain
their separate bounded coordination protocol.

## Prospective aggregate negative retirement

This extends reviewed repeat retention for a stopped reader with five exact native
sources. It is an implementation prerequisite, not an installed or live grant.
The owning aggregate binds all five source/correct-owner/payload preparations,
current complete catalog/census, the same existing Writer/thread and continuously
verified stopped-reader parent invocation. A private fsynced
`negative-retirement-v1.pending` marker binds one immutable aggregate intent.
Ordinary native, worker and archive preparation admission holds for valid,
malformed or inaccessible marker state. Serialized receipts and generic
allow-pending flags cannot grant continuation.

The source transitions are finite: one original alias, exact original/private
target aliases, then one retained private alias. Capture complete original parent
namespaces and project only the five approved participants. Shared parents must
account for every approved transition without adopting an unrelated file change.
Bytes, dev/ino/size/mtime/mode/uid/gid and xattrs remain bound. New ctime/nlink facts
are captured only at verified owned transitions. Complete catalog claim and
ancestor absence facts close directly after the last semantic callback and before
each syscall.

The reader phase carries the verified main/tasks pair, schema, eleven affected
rows, all-table typed fingerprints and independently verified raw restore custody.
All five staged native reservations precede exact reader SQL commit. Only the
five approved BOOK rows' `DELETED_DATE` and `LAST_MODIFIED_DATE` cells may change. Before commit, rollback removes
only exact staged aliases. After commit, exact SQL reversal precedes no-overwrite
source restoration. Unknown crash or lost-response state retains the marker and
originals without automatic replay.

Aggregate completion requires all five retired sources, matching committed
reader state, preserved proper owners, current complete census/catalog and durable
exact phase receipts. Only the owned marker can then be removed and its parent
fsynced under the same held Writer. A stopped owning parent separately verifies
service profile, databases and references before restart. Actual installed-image
checks, fresh full reader backup/restore and real NFS hardlink/fsync proof are
required before this protocol is executable.
