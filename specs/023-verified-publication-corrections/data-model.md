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
Authentication and ordinary startup exclusion require their separate API/native
integration tasks.

## Registration intent

Prepared immutable request/digest with exact reviewed evidence, current correct-owner/source bindings and expected registry revision. Prepare does not admit a correction. Commit is authenticated, explicitly accepts the exact intent token and recomputes current facts under writer exclusion. Stale intent stays uncommitted. Identical replay reconciles its existing attestation; changed evidence creates a new reviewed append-only transition.

## Guard proof

Protocol version, registry revision/census, candidate full SHA/stable filesystem signature, payload digest, exact proposed owner and decision (`unknown`, `allowed`, `review`, `unavailable`). A worker proof is advisory; native final admission recomputes actual staged content. Missing owner for a known payload stays review. Cached proofs require unchanged source/signature/revision and fresh matched correct-owner evidence.

## Repeat reconciliation receipt

Exact incorrect/correct paths and before/after hashes/attributes; restore-verified original and isolated-copy evidence; correction token and native owner comparison; retained duplicate destination outside scanned libraries; reader/native/catalog acceptance. It never invents a release failure or clears unrelated acquisition intent.
