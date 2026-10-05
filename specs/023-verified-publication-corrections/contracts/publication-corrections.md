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
