# Custom Mylar modules

Adapters are named for the behavior they own. `apply_patches.py` is the ordered
build manifest; `verify_image.py` uses the same manifest against an isolated copy.
Adapters check expected native source and fail on drift. Runtime helpers live in
Mylar's package; adapters and tests stay in the build stage.

| Responsibility | Build adapter | Runtime helper / focused tests |
|---|---|---|
| Discovery transport and preference | `patch_ddl_transport.py` | `ddl_transport.py`, `ddl_transport_worker.py`, `test_ddl_transport.py`; isolated curl runtime, Requests archive owner |
| Static-page notifications | `patch_global_events.py` | Guard absent page reload targets after displaying the notification |
| Active DDL path and size handling | `patch_ddl_status.py` | `test_ddl_status.py` |
| HTTP response validation | `patch_ddl_responses.py` | `test_ddl_responses.py` |
| Exhausted mirrors | `patch_ddl_exhaustion.py` | `test_ddl_exhaustion.py` |
| Transient mirror lookup failures | `patch_ddl_mirror_retries.py` | `test_ddl_mirror_retries.py` |
| Shared media writer ownership | `patch_media_writers.py` | `media_writer.py`, `native_writers.py`; lock, crash-fence and native admission tests |
| ComicTagger backend preference and availability | `patch_tagger_backend.py` | `tagger_backend.py`, `test_tagger_backend.py`; follows observer and handoff adapters |
| Native tagger result ownership | `patch_tagger_handoff.py` | `tagger_handoff.py`, `test_tagger_handoff.py`; follows native processing and monitoring adapters |
| ComicTagger timeout | `patch_tagger_timeout.py` | `test_tagger_timeout.py` |
| Unnumbered issue parsing | `patch_unnumbered_issues.py` | `test_unnumbered_issues.py` |
| HTTP resume offsets | `patch_ddl_resume.py` | `test_ddl_resume.py` |
| Requeued download state | `patch_ddl_requeue.py` | `test_ddl_requeue.py` |
| Authenticated publication registration and advisory protocol | `patch_publication_guard.py` | `publication_api.py`, `publication_guard.py`, `test_publication_api.py`; follows writer, workflow and naming helper installation |
| Native payload admission and durable import acknowledgement | `patch_publication_processing.py` (invoked by `patch_publication_guard.py`), `patch_postprocessing.py` | `publication_native.py`, `processing_guard.py`, `ordinary_import_history.py`, `ordinary_import_continuity.py`, `pp_monitor.py`; checked actual native processing, one-use delivery attempts, post-catalog acknowledgement and owned terminal continuity |
| Retained archive diagnostics and pure preservation proof | `patch_publication_guard.py` | `publication_archive_layout.py`, `publication_archive_derivative.py`, `publication_archive_repair.py`, `publication_archive_diagnostics.py`; pure preservation, stable-source and owning observer tests; ordinary inventory refusal remains review |
| Same-payload archive repair and review dispatch | `patch_publication_guard.py` | `publication_archive_reader.py`, `publication_archive_adoption.py`, `publication_archive_dispatch.py`, `publication_archive_history.py`, `publication_archive_verifier.py`, `publication_archive_rollback.py`, `publication_reader_lifecycle.py`, `publication_native_configured_scope.py`; portable adoption, lifecycle, configured-scope and owning API controls; genuine owning child and terminal acceptance remain required |
| Disabled retained-target acceptance | `patch_publication_guard.py` | `publication_retained_delivery.py`, `test_publication_retained_delivery.py`; original producer-process facts, no historical import acknowledgement; durable provenance and consumers remain unfinished |
| Disabled retained-pack finalization | `patch_publication_guard.py` | `publication_retained_finalize.py`, `test_publication_retained_finalize.py`; same-process catalog acceptance and exact member update, no historical acknowledgement or cleanup; restart provenance remains unfinished |
| Owned tagging publication and terminal evidence | `patch_publication_guard.py` | `publication_transaction.py`, `tagger_backend.py`, `tagger_native.py`, `tagger_service.py`, `tagger_pack.py`, `tagger_nfs.py`, `test_publication_tagging.py`; internal typed coordination, retained review and exact terminal completion |
| Owned release rename and root metadata | `patch_publication_guard.py` | `publication_rename.py`, `release_naming.py`, `tagger_supplement.py`, `publication_transaction.py`; `test_publication_rename.py`, `test_publication_maintenance.py`; immutable source/owner/census checkpoints and retained interruption holds |
| Existing-only startup admission and explicit fresh installation | `patch_publication_startup.py` | `native_writers.py`, `publication_fresh.py`, `test_publication_startup.py`; follows the authenticated publication API, refuses pending media intents and uncertain cleanup records |
| Reviewed retained repeat reconciliation | `patch_publication_reconcile.py` | `publication_reconcile.py`, `test_publication_reconcile.py`; exact registered conflict, private independently verified retention and conditional false-location removal; wanted intent remains separately reviewed |
| Conclusive combined-pass preservation cleanup | `patch_combined_publication.py` | `combined_cleanup.py`, `test_combined_cleanup.py`; independently captured producer history, current archive/owner/census and final reader acceptance, at-most-once private-pair retirement and passive terminal acknowledgement |
| Prospective canonical negative retirement and reader custody | `patch_publication_reader_cohort.py` | `publication_reader_cohort.json` pins the 25 canonical helpers; portable source controls and fresh installed origin/hash/type checks remain in the build stage; owning admission stays held while parent pin is absent |
| Explicit reviewed nested-metadata derivative | `patch_publication_derivative.py` | `publication_lineage.py`, `publication_derivative.py`, `library_metadata.py`; lineage/adoption/producer/consumer controls, complete inherited owner claims and retained originals; ordinary discovery does not authorize member-name changes |
| Disabled ordinary import continuity observation | `patch_ordinary_import_observation.py` | `ordinary_import_observation.py`; native copied originals and exact authenticated response closure; worker final post-cycle strict admission; process-local evidence only, durable pack/report and cleanup held |
| Disabled same-daemon retained finalization endpoint | `patch_retained_delivery_api.py` | `publication_retained_api.py`, typed `publication_retained_finalize.py` response; finite self-admitted hooks, original event registry required; no restart resurrection or import/cleanup/index grant |
| Authenticated health/recovery API | `patch_diagnostics_api.py` | `worker_health.py`, `failed_downloads.py`, `cooldown_health.py`; `test_health.py`, `test_failed_downloads.py`, `test_cooldown_health.py` |
| Transfer lifecycle and queue recovery | `patch_queue_control.py` | `queue_control.py`, `verified_transfer.py`; corresponding `test_*.py` |
| Mirror failover and cooldown discovery | `patch_ddl_failover.py` | `ddl_failover.py`, `test_ddl_failover.py`, `test_ddl_failover_native.py`; follows discovery and queue adapters |
| DDL progress | `patch_queue_progress.py` | `queue_progress.py`, `test_queue_progress.py` |
| DDL release labels | `patch_queue_labels.py` | `test_queue_progress.py`; follows queue ordering, retains linked issue identity |
| Queue policy and execution ordering | `patch_ddl_schedule.py` | `ddl_schedule.py`, `test_queue_schedule.py` |
| Queue diagnostics and import problems | `patch_queue_views.py` | `import_problems.py`, `worker_handoff.py`, `test_queue_views.py`, `test_worker_reports.py`; typed fresh diagnostic reports admitted before writes |
| Cooldown search fallback | `patch_search_cooldown.py` | `test_search_cooldown.py`, `test_search_fallback.py` |
| Prowlarr release identity and legacy failure isolation | `patch_prowlarr_identity.py` | `prowlarr_identity.py`, `test_prowlarr_identity.py` |
| Post-processing ownership and annual identity | `patch_postprocessing.py` | `processing_guard.py`, `test_pack_intake.py`, `test_file_matching.py` |
| Post-processing observations | `patch_pp_monitor.py` | `pp_monitor.py`, `archive_monitor.py`; corresponding `test_*.py` |
| Pack membership, catalog intake and publication evidence | `patch_pack_intake.py` | `pack_intake.py`, `pack_catalog.py`, `pack_bindings.py`, `tagger_pack.py`; `test_pack_intake.py`, `test_pack_records.py`, `test_pack_catalog.py`, `test_pack_bindings.py`; native naming and metadata retain exact confirmed members across publication |
| Preserve tracked series on startup | `patch_series_preservation.py` | `test_pack_intake.py` |
| Regular/annual identity and verified library presence | `patch_workflow.py` | `library_status.py`; workflow, queue-control and monitor tests |
| Activity, admission and DDL/NZB handoff | `patch_workflow.py` | `workflow.py`, `workflow_store.py`, `workflow_nzb.py`, `workflow_web.py`, `worker_handoff.py`; corresponding `test_*.py` and `test_publication_native.py`; typed worker acknowledgements, pack requests and atomic guided admission; one NZB fallback per exhausted single release, no-result remains Failed |
| Responsive queue interface | `patch_ddl_ui.py` | `ddl_queue.js`, `ddl_queue.css`, `test_ddl_ui.py` |
| Shared wide-screen layout | `patch_wide_layout.py` | `wide_layout.css` |
| SQLite write transactions | `patch_database_transactions.py` | `test_database_transactions.py` |
| Filename identity and single-volume recovery | `patch_file_matching.py` | `file_identity.py`, `test_file_identity.py`, `test_file_matching.py` |
| Explicit catalog volume labels | `patch_catalog_volumes.py` | `catalog_volume.py`, `test_catalog_volumes.py` |
| Story-arc search identities | `patch_story_arcs.py` | `story_arc_search.py`, `test_story_arc_search.py` |
| Wednesday release weeks | `patch_release_calendar.py` | `release_calendar.py`, `test_release_calendar.py` |
| Weekly release conflicts preserve wanted intent | `patch_weekly_identity.py` | `test_weekly_identity.py`; a mismatched feed entry cannot set a catalog issue to Skipped, and the weekly label explains that the release needs review |

`source_patches.py` contains only build-time source-boundary checks. It must not
be imported by the application. Existing marker strings remain stable where
behavior is unchanged; marker names are compatibility identifiers, not module
ownership names.

The transaction adapter follows upstream PR #57; filename year preservation
follows PR #66. Explicit volumes address issue #71, and story-arc dispatch addresses
issues #60–62. Single-volume matching adapts the intent of draft PR #32 with exact
title, actual catalog uniqueness, and single-main-file checks. Release weeks adapt
draft PR #24 for TalkHard while preserving Mylar's return fields and navigation
arguments. Legacy and file-pull modes retain their existing week keys, so this
does not rewrite stored pull records.
These refer to [MylarComics/mylar3](https://github.com/MylarComics/mylar3).

Do not combine unrelated fixes into a new batch module. Add an adapter at its
required dependency point, give behavior a focused runtime helper where needed,
and include regression checks in `verify_image.py`. Remove an adapter when a
verified base-image update provides its behavior natively.

## Modern tagger migration

`tagger_runtime.py`, `tagger_metadata.py`, `tagger_cli.py`, `tagger_archive.py`
and `tagger_adapter.py` provide bounded process, metadata, CLI, archive-reconciliation
and journaled publication boundaries for
the [migration](../../../specs/011-mylar-modern-tagger/plan.md).
They are build-tested and connected through the opt-in native Modern backend. The isolated
`/opt/comictagger` runtime is copied into the image, while Mylar continues using its
vendored legacy tagger. Tests: `test_tagger_runtime.py`, `test_tagger_metadata.py`,
`test_tagger_archive.py`, `test_tagger_adapter.py`, `test_modern_tagger.py`. The archive helper writes only new
operation files, reopens them for verification and never replaces a source.
`fetch_tagger_sources.py` runs only during image construction.
The publisher owns atomic CBZ exchange and versioned recovery receipts. Conflict
copies remain private for review. Its streaming recovery API skips cleaned history,
reports active locks without waiting, and retains malformed receipts. All five helpers are retained under
`/opt/mylar3-fixes` in the final image, with v1 exchange retained as a standalone compatibility helper. Native startup uses
the explicit v2 NFS publisher. Live rollout and rollback passed; optional DDL discovery has an independent Requests-default adapter.

`mylar.tagger_handoff` is the canonical native result module. It captures only
reconciled publication receipts, verifies the expected manual source, and keeps
in-place results out of automatic temporary-file placement. The final image does
not install a second standalone copy. Legacy tagging retains its string contract; Modern uses verified native producer results.

`install_tagger_service.py` installs package-relative helper imports and the
`mylar.tagger_service` producer. `tagger_lookup.py` bounds credential-bearing
ComicVine work in a child process and validates issue/volume identity. Service tests
cover manual/automatic ownership, no-overwrite, corruption and recovery admission.
The real-CLI gate exercises these native-package modules together. The service
requires the global writer coordinator. `tagger_native.py` owns catalog identity,
policy snapshots, bound recovery state and v2 publisher selection. `tagger_staging.py`
owns disposable output receipts and conservative cleanup. Startup recovery precedes
scans; complete native operations retain ownership through placement. Uncertain
staging remains private for review without claiming import success.

`tagger_backend.py` owns exact backend names, server validation and native dispatch.
The settings choice persists in the existing Metatagging section. Legacy remains
the default, and Modern is an experimental opt-in after integration acceptance.
Native jobs capture their backend at entry. Unsupported configured values return
an observed failure without invoking Legacy. The availability gate is a code
capability, not a user-controlled bypass flag.


`tagger_nfs.py` supplies the native version-2 rename/link publication strategy;
`tagger_attributes.py` owns bounded ACL/user-attribute preservation. The version-1
exchange publisher remains available for isolated compatibility tests. `test_tagger_nfs.py` covers real-process
crashes, conflicts, RPC ambiguity, native handoff and the pinned CLI. It can run on
an explicitly provided disposable media fixture root. Native journal selection,
startup recovery and writer/scanner admission are integrated. Live canary, startup
recovery and old-image rollback acceptance passed before opt-in activation.

`ordinary_import_history.py` records one-use delivery attempts in the private
`ordinary-import-v1.sqlite`, separately from immutable workflow controls. Only
the actual post-catalog importer hook emits completion; deferred source cleanup
requires it. Passive queue, guided and pack consumers join the original token,
owner, payload and current destination. `ordinary_import_ack.py` supplies the
normalizer's read-only counterpart. Existing archive presence, queue acceptance
and archive-repair reports do not create an ordinary import acknowledgement.

`publication_retained_delivery.py` is installed but disabled. It can create a fresh, bounded acceptance of a preserved existing target after an actual catalog event; it never creates a historical ordinary import acknowledgement. Current evidence is bound to the producing process. The source adds disabled primary-key POST `retainedDeliveryFinalize` and `retainedDeliveryStatus` hooks, with strict ordinary-purpose admission and typed response closure after serialization and writer release. Restart provenance, worker receipt consumption and matching installed semantic acceptance remain unfinished. It grants no placement, cleanup, Wanted-state or reader-index rights.

`ordinary_import_continuity.py`, installed by `patch_postprocessing.py`, retains
the original acknowledgement through an owned rename or preserved metadata
publication. Its separate private `ordinary-import-continuity-v1` journal records
the original pending receipt and actual terminal evidence without changing the
original completion row. Prepare the journal before the accepted operation backup
and include it with `ordinary-import-v1.sqlite` in backup and restore verification.
Missing or changed evidence remains review; a historical file without an original
import acknowledgement cannot gain one from rename or metadata history.

## Library metadata maintenance

`patch_library_metadata.py` follows converted-tagging installation and adds the idle
worker hook. `library_metadata.py` owns incremental catalog discovery and durable
repair admission. `metadata_repair.py` owns agreeing identity checks, provenance and
archive preservation. The explicit repair mode in `tagger_adapter.py` reuses v2
publication and recovery; normal archive/tagging paths remain strict. Settings live
in Activity and outcomes in the post-processing monitor. Focused coverage is in
`test_library_metadata.py` and `test_metadata_repair.py`.

Reader metadata supplements use `tagger_enrichment.py` and the explicit offline `tagger_supplement.py` preview/apply command. `test_tagger_enrichment.py` exercises real NFS publication, restored backups, preservation and a byte-stable repeat. The existing Modern service adds derived fields to future tags.
The coordinated `apply_preserved` entry point revalidates caller-owned original/restore copies and returns a native publication receipt without deleting them. Its tests cover reuse, stale/corrupt copies, linked copies, no-op retention and interrupted-token reconciliation.

## Release naming

`patch_release_naming.py` runs after file matching, writer coordination and workflow
installation. It installs `release_naming.py`, primary-key versioned proposal,
publication and status APIs, and the explicit final scanner-group/issue parser
adapter. It excludes the longest matching catalog title or registered alias
before reading a padded issue number, preserving numeric title suffixes and
fractional issues. An exact registered-title match also separates explicit print
run, padded number and publication year before native matching; collected types
retain their separate parser. `native_writers.py` reconciles its journal before every other native
writer while `release-v1.pending` exists. `release-state-v1.identity` binds the
workflow journal inode so missing recovery state cannot silently clear a fence.
The identical shared `media_writer.py` copies also block the optional worker while
native rename recovery remains pending. No native catalog schema changes are required.
Explicit version-2 replacements retain a rejected `retry_of` journal and bind
its complete digest in the new receipt. Source inode/attributes/hash and native
owner/status/year are revalidated; ordinary rejected-request replay stays blocked.


## Publication evidence and bootstrap foundations

`publication_guard.py` currently owns bounded stable archive inventories and
metadata-independent payload tokens, exact immutable attestation/census
validation and read-only final-marker checks. `workflow_store.protected_snapshot`
provides a complete versioned semantic projection for reviewed bootstrap;
volatile observation/event history, `meta.library_seen`, registration intents and
record update envelopes are excluded, while unknown record kinds stay protected.
`Store(existing_only=True)` is an opt-in connection foundation: it opens only an
existing private rollback-journal database, binds its inode and schema, and
rechecks loss, replacement and sidecars on every connection. It never creates
state, changes permissions or repairs schema. It does not validate correction
authority; the future native caller must acquire raw Writer before workflow
LOCK. Default callers retain existing behavior until the focused adapter lands.
`authority_status` is a passive internal probe using the existing raw Writer
before complete read-only authority validation. It reports fixed held reasons
and preserves media fences without replay, initialization or cached admission.
Zero timeout applies only to Writer acquisition, not the full snapshot check.
`observe_owners` adds an internal fresh native observer under caller-owned raw
Writer. It reads complete bounded rollback-journal catalog projections without
filtering deleted or inactive conflicts. Exact issue/annual IDs, parent/release
IDs and current lexical/physical path claims must be unique. All confined catalog
claims receive bounded metadata checks and rechecks, rejecting symlink aliases
and hardlink ownership conflicts without reading unselected archive payloads.
Only exact selected sources receive full SHA/signature and payload inventories.
Catalog changes, conflicting source payloads or stale sources hold the result.
The strict observed catalog v1 retains raw folder/location, canonical path,
status and annual deletion value. `publication_api.py` wires native observations
into primary-key-only POST `publicationControl` requests. The checked adapter
follows all writer/workflow helper installers. Strict bounded JSON rejects
duplicate keys, unknown fields, float/boolean integer aliases, deep structures
and caller filesystem locations before constructing state. Explicit bootstrap,
registration and typed journal recovery never invoke media replay. Prepare binds
the reviewed census and payload to fresh native facts; exact acceptance commits
only the retained token. Status optionally summarizes an exact receipt through
an existing immutable read-only connection. Responses exclude private manifests
and descriptions; advisory checks retain current and historical matched-owner
facts for worker revalidation. Digest-only advisory results cannot authorize
native publication. The startup adapter activates publication mode before native
database maintenance. Missing or invalid authority and pending media fences hold
initialization, workers and ordinary HTTP/API requests without replay. Health and
the authenticated publication controller remain available. Notification polling
requires admission because it writes native notification records. Successful
authority acceptance requires restart and successful native initialization before
media admission. `publication_native.py` computes fresh complete candidate and
matched-owner evidence locally under the caller's admitted raw writer. The
processing adapter guards native scripts, taggers, duplicates, call-specific
placement, the complete actual cleanup set and status/history writes. It
preserves distinct payload eligibility and carries a terminal retained review
through native processing acknowledgements without triggering failure search.
Registered original relocation or deletion remains held until the later verified
transition contract. Other native and worker publication boundaries remain
unfinished.
`publication_rescan.py` checks both parsed candidates and protected current
catalog bindings before parser corrections or row updates, including empty scans
and converted-archive repair. Retained review reaches the outer HTTP/API response
without invoking native failure fallback or acknowledging completion.
`publication_mutation.py` preflights actual manual renames, local downloads,
library imports and file-operation policies before moves, copies, links or
archival row updates. It checks exact payload eligibility and current unfiltered
correction-participant paths, including physical aliases and existing targets.
Copies to new destinations remain eligible; moving a catalog-bound protected
original remains held until verified relocation is implemented. An unbound import
cannot infer a known payload's owner from its filename. Tests:
`test_publication_rescan.py`, `test_publication_mutation.py` and the owning native
parser, converted-catalog and request suites.
`publication_transaction.py` binds each new tagging job to its admitted Writer,
source, policy, owner, correction census and captured pending-marker descriptor.
Only its active private capability can coordinate the producer. Exact terminal
Publisher and Staging evidence precedes owned fence clearance. A canonical proof
in the current receipt binds the private terminal witness, permitting historical
reads without replaying an older token or requiring a consumed temporary output.
Changed or unbound history remains held. Exact owned in-place metadata transitions
retain payload and catalog ownership, including registered archive updates through
fresh complete catalog claims and verified NFS before/displaced/after observation.
`publication_tagging_recovery.py` explicitly completes only an exact witnessed
terminal job after reviewed backup/restore attestation and fresh archive, receipt,
owner and full authority checks. Its private ledger and separate hold span each
clearance boundary; interrupted acceptance can resume without a media write or
producer invocation. Earlier phases and uncertain facts remain held. Other
direct Publisher consumers remain unfinished.
`tagger_adapter.py` also checks direct SDK entry and recovery before reading a
receipt or creating a workspace. `tagger_nfs.py` binds direct no-clobber restore
to the owned displaced source. `release_naming.py`, `tagger_supplement.py` and
`library_metadata.py` hold unbound correction-aware maintenance before publication
intents, fencing, replay or acknowledgement. Standalone supplementation checks existing
publication history without creating or recovering SQLite state. Tests:
`test_publication_maintenance.py` and the owning naming/metadata SDK suites.
Safe naming transitions and reviewed derivative aliases remain unfinished.
Owned Publisher receipt write failures cross the caller as retained review,
preserving prepared/displaced copies and admission holds without fallback replay.
`tagger_legacy.py` bounds the bundled 1.3.5 offline ComicRack CLI to an exact owned
CBZ workspace with private configuration and no conversion or upstream fallback
cleanup. The producer binds Legacy policy and backend identity to the receipt,
then rechecks actual payload after the child. Unsupported policies do not prepare
an intent; uncertain or unrepresentable output retains review. A released private
job can prove a changed registered metadata handoff through its exact immutable
terminal witness and fresh owner observations, granting no replay permission.
`publication_guard.py` is retained under
`/opt/mylar3-fixes`, with the immutable offline archiving-utils artifact.
`test_publication_guard.py` runs in the actual custom-image gate, including
ZIP, RAR4, RAR5 and 7z controls; its own authored payload fixtures require no
source-layout imports or network.

`RegistryState` adds explicit epoch preparation/acceptance and owned
prepared-marker → SQLite census/witness → final-marker writes under the raw
writer and workflow lock. Its digest-bound bootstrap plans preserve existing
fences and bind database/writer identities, schema, the complete protected
workflow projection and reviewed backup/restore attestations. Aborted intents
are terminal. Final publication requires the unchanged prepared marker and
complete committed census; missing state is held. The receipt history is bounded
to 128 bootstrap plans of at most 65,536 bytes each.

Real process-exit fixtures cover each write boundary. A process exit during an
uncommitted SQLite write leaves a rollback journal and remains held without
changing database/journal bytes during ordinary checks.

`JournalRecovery` prepares retained private database/journal/marker copies and
verifies SQLite recovery on an independent copy. Its complete restoration
snapshot includes every workflow record, update envelope and event row. Exact
plan acceptance precedes SQLite recovery of the original inode. Capture and
restoration evidence is fully revalidated before original SQLite access. The
pending recovery marker blocks ordinary bootstrap calls. A changed interrupted
pair requires a new reviewed plan linked to the prior accepted plan, with the
same independently verified restored contents. Captures remain retained, with
at most 128 recovery directories and 256 MiB per database/journal input.

Read-only census validation now requires an exact committed registration receipt
for every attestation and the matching attestation for every committed receipt.
Typed plans hash the attestation body without its intent first, then derive the
materialized attestation and new census. The complete predecessor chain must
match the final census. Accepted unfinished receipts hold admission. Committed
receipts bind original database/writer identities and the workflow schema.
Registration history allows 640 receipts of at most 4 MiB each, alongside the
128 bootstrap receipts and 512 attestations. The aggregate namespace remains
bounded to 32 MiB. Historical owner observations still require fresh native
validation before registration or admission.

The installed primary-key API now connects registration to the native observer
and exact receipt operations. Startup/media admission enforcement remains
unfinished in feature 023. These helpers perform no automatic initialization,
recovery, correction registration or media publication during image startup.

`RegistrationState` adds internal bounded preparation, exact token acceptance,
atomic attestation/census/committed receipt writes and prepared/final markers.
A trusted observer runs under the raw writer before workflow LOCK and must
return the exact reviewed inventory and owner observations. The authenticated controller now supplies the native observer; it never accepts
caller observations as current native proof. Accepted-old
and prepared-old recovery require fresh observations to commit or explicit
abort. Prepared-new recovery validates the complete committed chain. Abort
restart retains terminal receipts. Registration journals require explicit `RegistrationJournalRecovery` and remain
held unchanged during ordinary checks. These
internal methods are not exposed or executed during application startup.

`RegistrationJournalRecovery` reuses the retained capture/isolated restoration
protocol through its distinct registration-journal receipt type. It verifies the
accepted registration predecessor, complete prior chain and original bootstrap
witness against the original identities/schema/workflow/fences and exact
prepared marker. Recovery restores only old SQL state. Fresh registration
observation or explicit abort remains a separate step. Bootstrap receipts cannot
cross the registration route. Canonical JSON comparisons reject boolean/float
aliases in markers and retained receipt predecessors. Native observation, API
authentication and startup exclusion are installed in source. Per-payload
publication enforcement and matching live rollout remain unfinished.

`publication_fresh.py` supplies explicit `prepare-fresh` only for an already owned,
empty state root under early startup exclusion. Existing native/workflow catalogs,
writer directories, claims or SQLite sidecars refuse this route. Preparation
retains an exclusive private claim and partial state on failure. Exact bootstrap
acceptance is still required. First native catalog creation consumes the accepted
fresh claim before `dbcheck`; a crash cannot grant another creation attempt.
Existing startup requires an owned regular readable native catalog with no pending
SQLite sidecars. Missing or damaged native catalogs stay held for reviewed recovery.
Workflow factories use existing-only SQLite under caller-owned admission. DDL
retry state keeps its separate JSON Store and existing attempt/cooldown records.


## Combined publication and owned conversion

`patch_combined_publication.py` installs the primary-key POST `combinedPublication` route after publication authority. `combined_publication.py` owns private preparation and the finite rename → unchanged-hash reader restoration → preserved root metadata sequence. `publication_transaction.closed_supplement` validates closed metadata lineage without creating or replaying a tagging transaction. Private originals remain retained; final cleanup requires separate acceptance.

The same route accepts a read-only `preview` action with exact `naming` and `policy` arguments. `combined_publication.preview` derives additions through `tagger_enrichment.supplements` under fresh native source, owner and complete census proof without creating a journal or capability. Reviewed preparation supplies both that immutable preview and `approved_additions`; native equality checks precede copies and preparation, and actual additions are checked again before tagging. Empty canonical previews create no publication. `combined_preview=1` requires the installed preview and route; the image gate checks module parity and the callable. Legacy explicit combined manifests retain their existing contract.

`patch_publication_conversion.py` installs primary-key `commitConvertedArchive` and passive `convertedArchiveStatus`. `publication_conversion.py` owns exact live conversion admission, unchanged member/page inventories, private original retention, exclusive target publication, conditional catalog relocation and durable terminal acknowledgement. Its controls use actual archive verification and current native ownership. PDF and member-name derivatives remain held. Both routes are installed and tested by the image gate before workflow capabilities are advertised.

Archive diagnostics run only after ordinary inventory refuses the same source.
`archive_diagnostics=1` advertises installed diagnostic functions. Fixed status
and reason text reaches retained postprocessing history without source paths,
hashes or member content. The pure ZIP32 directory spelling handler verifies
preservation in disposable controls; returned bytes grant no publication rights.
Native preparation and reader-backed adoption require the separate
[archive repair contract](../../../specs/024-verified-archive-repair/contracts/archive-repair.md).


`publication_archive_owned.py` and `publication_archive_prepare_routes.py` install
primary-key `publicationControl` PREPARE and passive status for the strict lossless
ZIP repair. They use the current catalog, existing Writer and exclusive private
custody; every execution/adoption/reader grant remains false. Partial evidence
retains review without replay. Adoption request/status actions queue review only;
connected owning adoption remains held.
Any `negative-retirement-v1.pending` marker denies ordinary Writer entry, native
startup/admission, worker evidence and repair preparation/status, including
malformed or inaccessible markers. Existing recovery flags do not bypass it.
Only the future aggregate's exact typed continuation may carry its already held
Writer through a phase; these modules do not install that continuation.

The exact reversed adoption can be consumed by
`publication_archive_rollback.from_reversed(...).clear()` under its original
Writer and reader lifetime. Its durable terminal successor precedes marker
removal and remains held after unknown acknowledgements. The independent
`verify_rollback_existing` checks original source, catalog and reader state,
with type-sensitive rollback receipt joins. `archive_repair_rollback=1`
advertises these installed functions only; import, reader-index and publication
acceptance remain separate. Saved receipts cannot recreate the typed consumer.

The separate canonical `publication_archive_preparation_existing.from_existing`
factory derives one completed stage from the exact Controller, owner and operation
ID. Genuine stopped custody must carry the original preparation metadata full9
and completed stage directory full9. The factory independently recomputes the
source witness, derivative, restore, catalog, census and policy before constructing
the actual owning `RepairPreparation`; saved JSON supplies no authority. Missing
historical directory provenance, changed incarnations and partial stages stay
held. This installs no API replay, new operation, Writer bypass or acceptance grant.

The independent archive verifier also returns factual vectors for forward or
rollback observation: original files, ancestors, catalog claims, namespace
censuses and required absences. This includes every other comic examined by the
ownership policy. The verifier closes those original facts after all semantic
callbacks; the returned vectors grant no import, reader-index or resume right.

## Prospective reader cohort installation

`patch_publication_reader_cohort.py` follows the existing adapters and installs
21 reader runtime helpers, checking the archive-owned, lifecycle and
configured-scope helpers already installed by publication authority. The lifecycle
retains original preparation file and directory facts through its same-custody
binding. Admission upgrades accept only the exact reviewed legacy and immediate
predecessor bytes; unknown implementations remain refused.
`publication_reader_cohort.json` pins all 25 exact canonical package files. The
catalog helper is installed as `mylar.publication_negative_catalog`; package
imports share the existing guard, mutation, API and Writer module identities.
All additional SDK closure helpers retain their existing owning adapters.

`run_publication_reader_controls.py` runs each portable mechanical suite in a
separate process on an isolated source copy. The immutable namespace kernel
requires its explicit local fixture actor at UID 1000; a root build drops only
these children to that identity and gives their private kernel copy mode 0600.
The installed-source gate retains its original image identity. `fixtures/` and the portable marker are build-only inputs;
no fixture or test is installed in Mylar's runtime package.
`verify_publication_reader_cohort.py` uses a fresh isolated interpreter to check
actual installed origins, exact bytes, embedded dependency hashes, namespace
kernel loading, SDK identities and the SQL function alias. This source and
identity proof grants no owning execution or publication acceptance.
`publication_reader_admission.PARENT_SHA` remains `None`; the owning parent,
provider/terminal acceptance, actual connected factories and NFS/reader
acceptance remain separately reviewed requirements.

The read-only scoped reader recovery provider, terminal observer, proof producer,
backup/rows/schema primitives and their predecessor fixtures live under
`reader_recovery/`. They are host tools and temporary source mounts for a
selected child; the final image does not install them in Mylar or add a mount.
`run_reader_recovery_controls.py` tests this explicit source closure during the
existing isolated image gate. The canonical birth helper is installed with the
reader cohort; checked SDK source/origin identity and the same inherited pipe
remain mandatory. Admission retains a null parent pin until the owning parent
and its fresh proof producers are independently accepted.

The host-only recovery tree also contains the continuous lifecycle parent,
fresh native process/evidence producer and schema1 phase-custody composer.
The private-copy gate runs 588 recovery checks in isolated suite processes,
including explicit predecessor fixtures and the current provider command
contract. Original reader pair signatures are carried unchanged; the actual
child lifecycle validates its own kernel facts. No new pair protocol or
namespace assumption supplies authority. The parent pin remains unset;
independent terminal/NFS producers and actual protected integration remain
required. These tools add no runtime package module or permanent mount.

The terminal observation producer retains the original owning execute ACK and
report references through fresh observation and terminal custody. Its exclusive
private outputs retain their original inode and mode through final checks. Both
forward and rollback layouts remain factual observations; owning runtime proof
and publication acceptance are separate gates.

`publication_archive_history.py` retains bounded factual preparation, execution
and independent verification receipts in `Controller.root/archive-history-v1`.
The explicit repair-request preflight initializes this private journal under
the native Writer before queue admission; include it in the subsequent consistent
backup and protected custody capture. Passive status requires existing history
and preserves the original records and namespace through its final raw closure.
These facts grant no ordinary import, publication, indexing, replay or resume
permission. Original child namespace differences remain a separate acceptance
gap; copying or restamping receipts does not resolve it.

`publication_retained_finalize.py` remains disabled. A live retained-target acceptance can finalize one exact pack member and a distinct backend record in the same process. Saved records cannot restore the original producer witness after a restart or unknown commit. This state grants no ordinary import acknowledgement, source cleanup, or reader-index acceptance; authenticated activation and downstream acceptance remain unfinished.

The default-disabled retained-pack parent and backup helper live under
`reader_recovery/`, with a byte-identical adjacent worker control dependency.
They are host tools; the installer does not add them to the canonical Mylar SDK.
The worker image includes only the production control and exact handoff successor.
The copied API graph explicitly admits four host dependencies and 37 worker
Python fixture files plus their source map. Its all-family gate runs 247 controls,
including 48 parent conversation checks, against the generated API fixture.
Export/composed API suites are not repeated directly without that fixture. The
parent remains disabled and its accepted runtime pins unset; tested factual
results do not authorize reader resume, indexing, cleanup or historical import.
