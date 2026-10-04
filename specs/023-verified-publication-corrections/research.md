# Research: Verified publication corrections

Inspected baseline: `d0120332b5529e2f9d3c751a2e5ffce48b4945f6`. This is prospective source design, not a claim of deployed prevention. Private evidence remains outside Git.

## Durable correction authority

**Decision**: Mylar owns an immutable correction registry in its existing private workflow database, with a complete census/revision and a separately bound writer-protocol marker. Authenticated explicit operational admission requires a reviewed attestation, current correct-owner proof and exact archive hashes. No automatic registration from archive metadata or worker reports.

**Rationale**: Private repair receipts already prove past corrections, but imports do not consume them. Clearing a false assignment alone permits the same payload to return. Bounded recent history or truncated `Store.all()` is not authoritative coverage. Registration/index/census commit in one SQLite transaction; the filesystem marker uses a separate prepared → SQLite commit → final-marker protocol with exact-old/exact-new reconciliation. An immutable epoch and explicit authenticated bootstrap bind existing writer state to reviewed workflow/backup facts. Both absent on an existing writer is uninitialized, not auto-empty. Authenticated application bootstrap/status can remain available while all media mutation and pending replay are held. Local state cannot detect a coherent rollback of both database and marker; require independent restore evidence and operator reconciliation.

**Alternatives**: Full archive SHA is changed by retagging/recompression. Issue or provider blacklists would block genuine releases. Filename/internal-folder heuristics do not replace reviewed content evidence. A worker-owned registry would leave direct native and disabled-tagging imports exposed.

## Payload verification and archive formats

**Decision**: Reuse the same immutable archiving-utils artifact already pinned by the normalizer; bundle its offline archive reader with Mylar and the distribution libarchive runtime. Obtain a bounded CRC/integrity-verified complete archive inventory without extraction or source writes. Check actual native-image compatibility in CI before delivery.

**Rationale**: Mylar's existing `tagger_archive.snapshot()` verifies ZIP only. Four current repeats are CBR. A ZIP-only guard or a worker-only conversion guard leaves direct native CBR/CB7 paths uncovered. The pinned tool has RAR4/RAR5 checksum verification, link/encryption/path rejection, member/expanded-size limits and streaming libarchive readers. The `archive-list` read path does not call its Python-3.11-only whole-file digest helper; actual native-image tests must still prove compatibility. No unverified dependency or network fetch occurs at runtime.

**Contract choice**: Payload identity includes every regular non-root-metadata member's exact validated name, size and full SHA, plus the recognized page ordering. Include all sidecars. Empty directory entries are separately recorded/preserved but excluded from the comparison token: they contain no publication bytes and are represented differently in RAR and verified CBZ conversion. Reject nonempty directory payloads, duplicates and ambiguous metadata. Exact member-name changes require explicit verified aliases; perceptual matching/OCR is outside scope. Any unsupported, changing or oversized inventory is held whenever the validated registry is nonempty; it cannot be assumed unknown. Only a complete validated empty registry permits ordinary eligibility without a scan.

## Native admission coverage

**Decision**: Check concrete archive and claimed owner before scripts/tagging in every postprocessor branch, and revalidate the bound source before placement and status commits. Return a terminal retained-review result rather than an ordinary tagging failure. Also guard rescan, converted catalog reconciliation, manual/backend tagging, naming admission/recovery and metadata publication.

**Rationale**: Published native `PostProcessor` has ordinary, storyarc and oneoff branches; disabled tagging skips the tagging adapter, and failed tagging can continue to `file_ops` and Downloaded/Location writes. `processing_guard.run` owns the shared writer but lacks the final member/owner binding. `file_identity.validate_rescan` and `converted_catalog.update` can independently assign ownership. `release_naming.finish` and supplemental publisher recovery can commit after interruption.

**Inspection sources**: `patch_postprocessing.py`, `processing_guard.py`, `tagger_backend.py`, `tagger_native.py`, `tagger_service.py`, `file_identity.py`, `converted_catalog.py`, `converted_tagging.py`, `release_naming.py`, `tagger_supplement.py`, `patch_media_writers.py`; exact pinned native source and branch fixtures are verified by `verify_image.py`.

## Worker contract and lock order

**Decision**: Native authority provides a versioned primary-key advisory check; the worker recomputes local payload evidence and binds its decision to the registry revision/source signature. Perform remote checks before taking the shared writer, then validate the complete census/marker and unchanged epoch/revision plus fresh matched correct-owner all-row/path/archive evidence through existing read-only config/media and narrow writer mounts under exclusion. Revision alone does not preserve advisory owner truth; worker-only confirmation/cleanup/conversion must perform this full local revalidation. Final native import checks independently recompute staged bytes.

**Rationale**: An API request that waits for the shared writer while the worker holds it would deadlock. Advisory caller digests cannot authorize native publication. Existing config/media/cache/writer mounts are sufficient; do not add writable native SQLite mounts. Cover common `import_recovery.submit`, guided/pack routes, already-existing target confirmations, Extras preservation, duplicate cleanup, conversion publication and naming/metadata passes.

## Registration and existing repeats

**Decision**: Implement bounded prepare/commit admission with an immutable exact reviewed intent and expected registry revision. Require current unambiguous native correct owner, matching current payload and explicit private evidence attestation before commit. Keep historical proof/allowed-owner changes append-only and reject contradictory owner sets.

**Rationale**: Native Mylar cannot independently read private historical worker receipts through an unrequested mount. A scoped authorized importer must verify backup/restore/journal/independent publication evidence and attest it; native recomputes current facts and authenticates admission. Reconciliation is separate: preserve current repeats outside scanned libraries, retain the correct copy, and compare-and-swap only proved false claims. Unknown acquisition provenance cannot justify failed-release reporting.

## Operational limits

**Decision**: Source development, isolated tests and image publication may proceed while privileged access is paused. Live registration, state/media repair, worker resumption and final cleanup require a fresh application-consistent backup and isolated restore when the access restriction is lifted.

**Rationale**: Native acquisitions continue despite external/default-worker holds. No ordinary primary API establishes a complete writer freeze; per-comic pause and DDL policy toggles cannot safely substitute for quiescence. Current-library inventory drift remains diagnostic evidence.


## Payload foundation implementation boundary

The foundation calls the pinned artifact's offline native decoder module in an
isolated, resource-bounded child rather than its general CLI. This permits
bounded in-memory root metadata syntax validation while retaining native RAR
header/CRC checks. It performs no extraction or configuration lookup. ZIP and
plain TAR use bounded Python readers; compressed TAR wrappers are unavailable
because a partial TAR reader cannot prove the wrapper trailer. Input hashing
and child verification share one deadline and finite byte/output limits.
Runtime compatibility remains unverified until the actual custom-image gate.
