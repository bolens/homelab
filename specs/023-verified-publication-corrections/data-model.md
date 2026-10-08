# Data model: Verified publication corrections

## Immutable correction attestation

Version, deterministic token, complete canonical regular-member inventory and digest, separately preserved directory inventory, allowed/rejected owner tuples, reviewed evidence digest and description, observed correct sources/full SHAs, creation time and prior registry revision. Owners include native table, issue ID, parent comic ID and annual release comic ID where applicable. Attestations append; contradictory allowed/rejected sets cannot overwrite earlier evidence.

## Registry census

Version, monotonically increasing revision, exact attestation keys/count and canonical census digest. Read every required record without recent-history pagination. Registration/index/census changes share one SQLite transaction; the marker has a separate prepared → SQLite commit → final-marker durability protocol defined in the interface contract. Bind an immutable initialization epoch. Missing either side, mixed revisions or both absent on existing writer state require authenticated bootstrap/recovery and block media admission; no automatic empty fallback. Startup exposes initialization/status without replaying pending media until initialized. A matching rollback of both sides still requires independent backup/epoch evidence and explicit operational reconciliation.

## Bootstrap receipt

A `publication_intent` record contains an immutable digest-bound bootstrap plan
and a finite acceptance/outcome envelope. The plan records the selected epoch,
empty target census, existing database inode and writer root/lock identities,
schema digest, protected workflow snapshot, unchanged pending-fence signatures
and explicitly reviewed backup-manifest/independent-restore digests. At most
128 plans of 65,536 bytes each are supported by the bootstrap foundation.
Prepare stays unaccepted; explicit acceptance precedes the durable prepared
marker. Outcomes move from prepared to accepted, then committed or aborted;
aborted receipts cannot initialize again. The final marker references the sole
committed initialization witness. Missing witness, foreign identities or changed
schema holds admission. Later registration intents require their separate
reviewed transition implementation.

## Journal recovery receipt

A private owned recovery marker records an immutable digest-bound plan and an
outcome of verified, accepted or recovered. The plan binds the exact original
database/journal/marker signatures and full hashes, writer identity, unchanged
pending fences, bootstrap token and retained capture directory. Independently
restored database bytes and complete SQL contents have separate digests. The
SQL comparison includes all record values, update envelopes and event rows.
Strict nested shapes, types, sizes and owned-file evidence are required before
acceptance. The retained restored database is reread with full integrity and SQL
equality checks before original SQLite access.

Original database/journal inputs are bounded to 256 MiB each, with at most 128
retained recovery directories. The original database inode is preserved. A
pending recovery marker blocks ordinary bootstrap. If a rollback interruption
changes the pair, a new explicit review records the preceding accepted plan's
digest and proves the same complete restored contents. Captures and completion
receipts remain retained for operational acceptance and later scoped cleanup.
Authentication is wired by the checked primary-key adapter. Startup exclusion
is integrated separately from the remaining per-payload publication guards.

## Registration intent

Prepared immutable request/digest with exact reviewed evidence, current correct-owner/source bindings and expected registry revision. Prepare does not admit a correction. Commit is authenticated, explicitly accepts the exact intent token and recomputes current facts under writer exclusion. Stale intent stays uncommitted. Identical replay reconciles its existing attestation; changed evidence creates a new reviewed append-only transition.

Registration plan v1 contains exactly `version`, `action=register`, the complete
`old` census, the original filesystem/schema/workflow/fence `binding`, and the
attestation `body` without `intent`. Hash that plan first, insert its token as the
attestation intent, then derive the attestation key and next census. Neither the
materialized attestation key nor the next census participates in the plan hash.
The receipt envelope contains only `plan`, `accepted` and `outcome`.

Read-only validation requires one committed registration receipt per attestation
and one attestation per committed registration receipt. Each plan's old census
must equal the preceding complete census, starting with the initialized empty
epoch. The derived final census must equal the stored census and final marker.
Accepted unfinished receipts hold admission. Prepared and aborted receipts
retain history but cannot authorize an attestation. Committed receipts also bind
the original database/writer identities and current workflow schema. Historical
workflow projections and owner observations require fresh checks at registration
and admission. Receipt shape alone does not authenticate an observation.

Bounds are 512 attestations, 128 bootstrap receipts of at most 65,536 bytes each,
640 registration receipts of at most 4 MiB each, and 32 MiB across the complete
publication namespace. Exhausted history holds without automatic pruning.
Internal registration writes now follow explicit acceptance and prepared-marker,
SQLite and final-marker durability. The internal native observer is implemented;
the authenticated controller now supplies native observation. Startup enforcement
remains open.

Observed catalog v1 contains exactly `version=1`, `comic_location`, `location`,
canonical absolute `path`, `status` and `deleted`. Path strings are nonempty and
at most 4,096 UTF-8 bytes. Status is Downloaded or Archived. Regular deletion is
null; annual deletion retains its raw null or integer zero. Boolean/float aliases,
extra fields, traversal and mismatched raw/canonical paths are invalid. The
outer facts retain the exact owner tuple, full source SHA and nine-field signature.
These facts are historical attestations; registration and publication still
require fresh native observation.

## Registration journal recovery receipt

Typed `registration-journal` plans use `registration_token` and retain the same
bounded private capture, independent restoration and explicit acceptance protocol
as bootstrap journal recovery. The two receipt types cannot cross recovery
routes. A restored registration predecessor must contain its accepted intent,
complete prior correction chain and original committed bootstrap witness, with
matching original database/writer/schema/workflow/fences and prepared marker.
Recovery preserves all workflow records, envelopes and events. It restores only
the accepted old state. Registration still requires separate fresh observation
or explicit abort. Interrupted rollback requires a new linked isolated review.
Authority markers and receipt predecessors compare canonical JSON so boolean
and floating-point substitutions cannot alias integer protocol values.

## Guard proof

Protocol version, registry revision/census, candidate full SHA/stable filesystem signature, payload digest, exact proposed owner and decision (`unknown`, `allowed`, `review`, `unavailable`). A worker proof is advisory; native final admission recomputes actual staged content. Missing owner for a known payload stays review. Cached proofs require unchanged source/signature/revision and fresh matched correct-owner evidence.

## Fresh installation claim and startup admission

The private version-1 fresh claim binds the existing owned root identity, reviewed
epoch/backup evidence and exact bootstrap token. Its durable phases are `creating`,
`prepared` and `native-creation-started`. The last phase consumes first native catalog
creation permission before any native database write. Interrupted partial state stays
held and cannot infer another fresh installation. Existing catalogs must remain owned,
singly linked, complete readable rollback SQLite files with native base tables.

Publication authority is checked under raw Writer before workflow LOCK on every
native admission. Successful native initialization is a separate process-local startup
condition. Registry acceptance requires restart before ordinary workers/API/UI admission.
Passive health and explicit authenticated review do not create catalogs or replay media.

## Repeat reconciliation receipt

Exact incorrect/correct paths and before/after hashes/attributes; restore-verified original and isolated-copy evidence; correction token and native owner comparison; retained duplicate destination outside scanned libraries; reader/native/catalog acceptance. It never invents a release failure or clears unrelated acquisition intent.

## Prospective negative aggregate

An immutable batch binds five exact source/owner/payload preparations, one complete
census/catalog, original complete shared-parent namespaces, retained original/restore
custody, one existing held Writer/thread and one verified stopped-reader lifetime.
Each member has a finite original/staged/retired phase and exact inode alias count.
A durable aggregate marker and per-member intent/receipt records retain unknown
interruption states. The reader envelope binds physical main/tasks pairs, schema,
all typed tables and eleven affected rows, with exactly five approved BOOK rows' `DELETED_DATE` and `LAST_MODIFIED_DATE`
changes and their exact reversal. Terminal clearance requires the complete batch,
not independently completed-looking member receipts. An exact root-owned terminal
successor hold becomes durable before aggregate-marker removal; ordinary and
startup admission refuse unresolved successor state until its owning terminal
phase durably acknowledges completion.
