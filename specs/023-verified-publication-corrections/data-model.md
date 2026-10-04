# Data model: Verified publication corrections

## Immutable correction attestation

Version, deterministic token, complete canonical regular-member inventory and digest, separately preserved directory inventory, allowed/rejected owner tuples, reviewed evidence digest and description, observed correct sources/full SHAs, creation time and prior registry revision. Owners include native table, issue ID, parent comic ID and annual release comic ID where applicable. Attestations append; contradictory allowed/rejected sets cannot overwrite earlier evidence.

## Registry census

Version, monotonically increasing revision, exact attestation keys/count and canonical census digest. Read every required record without recent-history pagination. Registration/index/census changes share one SQLite transaction; the marker has a separate prepared → SQLite commit → final-marker durability protocol defined in the interface contract. Bind an immutable initialization epoch. Missing either side, mixed revisions or both absent on existing writer state require authenticated bootstrap/recovery and block media admission; no automatic empty fallback. Startup exposes initialization/status without replaying pending media until initialized. A matching rollback of both sides still requires independent backup/epoch evidence and explicit operational reconciliation.

## Registration intent

Prepared immutable request/digest with exact reviewed evidence, current correct-owner/source bindings and expected registry revision. Prepare does not admit a correction. Commit is authenticated, explicitly accepts the exact intent token and recomputes current facts under writer exclusion. Stale intent stays uncommitted. Identical replay reconciles its existing attestation; changed evidence creates a new reviewed append-only transition.

## Guard proof

Protocol version, registry revision/census, candidate full SHA/stable filesystem signature, payload digest, exact proposed owner and decision (`unknown`, `allowed`, `review`, `unavailable`). A worker proof is advisory; native final admission recomputes actual staged content. Missing owner for a known payload stays review. Cached proofs require unchanged source/signature/revision and fresh matched correct-owner evidence.

## Repeat reconciliation receipt

Exact incorrect/correct paths and before/after hashes/attributes; restore-verified original and isolated-copy evidence; correction token and native owner comparison; retained duplicate destination outside scanned libraries; reader/native/catalog acceptance. It never invents a release failure or clears unrelated acquisition intent.
