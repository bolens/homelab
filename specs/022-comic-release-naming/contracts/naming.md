# Naming and migration contract

Default configuration: `release_naming.enabled=false`, bounded `batch_size=1`. Enabled operation requires existing absolute shared writer state, Mylar configuration and reader integration.

Primary-key native capability/proposal requests resolve existing catalog ownership and native filename evidence. A versioned rename request carries its proposal/token, old path, desired basename, expected SHA-256 and exact issue/parent ownership. Unsafe/linked paths, contradictory metadata, unproven years, sidecars and case-insensitive collisions fail closed.

A regular catalog row with no parsed filename year may use matching embedded Year and stored issue date only with the exact canonical ComicVine issue link. Missing metadata/link evidence and explicit filename-year contradictions remain held. This does not relax annual identity restoration or infer a series start year.

The renderer emits `Series.Name[.vN][.Annual].NNN.(YYYY)[.(Labels)]-Group.cbz`; missing group is omitted. Collected volumes retain their collected type/edition and volume distinction. Fraction and variant numbers retain their meaning. Actual catalog/year contradictions require publication review. Group internal hyphens are preserved; spaces become dots. No URL, API key or guessed scanner group is introduced.

Native publication and catalog updates occur under the existing writer protocol with a durable rename recovery fence. Other writers must reconcile unfinished native rename receipts before admission. Same-folder publication keeps archive bytes, inode attributes and existing status; no destination is overwritten.

Ordinary requests remain version 1. An explicit replacement is version 2 with the same fields plus `retry_of`, the exact rejected predecessor token. Its own token includes that field and version. The native owner requires the predecessor to remain rejected, its source/hash/issue/parent to match, and its original inode/attributes/table/status/year to remain valid. The child stores a digest of the entire predecessor and never replaces it. Replay of the rejected request stays forbidden; only committed child acknowledgement is idempotent. The worker's explicit `recovery_entry` requires the held receipt, both private hash/CRC-verified copies and unchanged reader identity/progress before preparing fresh copies. Ordinary planning/ticks do not invoke it.

The worker verifies Komga's recorded hash against actual source bytes and checks for duplicate/deleted restoration candidates before mutation. Reader scan and final readiness/progress proof follow native commit. An uncertain submission retains copies and reconciles the native receipt/actual catalog before any further action. Live bulk work requires a fresh reviewed manifest and restore-verified persistent-state backups.

Combined-pass holds can retain receipt-bound hardlinks in both naming and joint folders. Keep them intact. Supply a fresh private detached pair from the restore-verified recovery backup to `recovery_entry`; shared or linked copies are never accepted as its preservation set. Replacement reconciliation rechecks the predecessor digest before any mutation or fence clearance.
