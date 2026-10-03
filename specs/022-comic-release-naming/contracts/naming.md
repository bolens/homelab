# Naming and migration contract

Default configuration: `release_naming.enabled=false`, bounded `batch_size=1`. Enabled operation requires existing absolute shared writer state, Mylar configuration and reader integration.

Primary-key native capability/proposal requests resolve existing catalog ownership and native filename evidence. A versioned rename request carries its proposal/token, old path, desired basename, expected SHA-256 and exact issue/parent ownership. Unsafe/linked paths, contradictory metadata, unproven years, sidecars and case-insensitive collisions fail closed.

A regular catalog row with no parsed filename year may use matching embedded Year and stored issue date only with the exact canonical ComicVine issue link. Missing metadata/link evidence and explicit filename-year contradictions remain held. This does not relax annual identity restoration or infer a series start year.

The renderer emits `Series.Name[.vN][.Annual].NNN.(YYYY)[.(Labels)]-Group.cbz`; missing group is omitted. Collected volumes retain their collected type/edition and volume distinction. Fraction and variant numbers retain their meaning. Actual catalog/year contradictions require publication review. Group internal hyphens are preserved; spaces become dots. No URL, API key or guessed scanner group is introduced.

Native publication and catalog updates occur under the existing writer protocol with a durable rename recovery fence. Other writers must reconcile unfinished native rename receipts before admission. Same-folder publication keeps archive bytes, inode attributes and existing status; no destination is overwritten.

The worker verifies Komga's recorded hash against actual source bytes and checks for duplicate/deleted restoration candidates before mutation. Reader scan and final readiness/progress proof follow native commit. An uncertain submission retains copies and reconciles the native receipt/actual catalog before any further action. Live bulk work requires a fresh reviewed manifest and restore-verified persistent-state backups.
