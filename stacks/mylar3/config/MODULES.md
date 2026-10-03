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
| Authenticated health/recovery API | `patch_diagnostics_api.py` | `worker_health.py`, `failed_downloads.py`, `cooldown_health.py`; `test_health.py`, `test_failed_downloads.py`, `test_cooldown_health.py` |
| Transfer lifecycle and queue recovery | `patch_queue_control.py` | `queue_control.py`, `verified_transfer.py`; corresponding `test_*.py` |
| Mirror failover and cooldown discovery | `patch_ddl_failover.py` | `ddl_failover.py`, `test_ddl_failover.py`, `test_ddl_failover_native.py`; follows discovery and queue adapters |
| DDL progress | `patch_queue_progress.py` | `queue_progress.py`, `test_queue_progress.py` |
| DDL release labels | `patch_queue_labels.py` | `test_queue_progress.py`; follows queue ordering, retains linked issue identity |
| Queue policy and execution ordering | `patch_ddl_schedule.py` | `ddl_schedule.py`, `test_queue_schedule.py` |
| Queue diagnostics and import problems | `patch_queue_views.py` | `import_problems.py`, `test_queue_views.py` |
| Cooldown search fallback | `patch_search_cooldown.py` | `test_search_cooldown.py`, `test_search_fallback.py` |
| Prowlarr release identity and legacy failure isolation | `patch_prowlarr_identity.py` | `prowlarr_identity.py`, `test_prowlarr_identity.py` |
| Post-processing ownership and annual identity | `patch_postprocessing.py` | `processing_guard.py`, `test_pack_intake.py`, `test_file_matching.py` |
| Post-processing observations | `patch_pp_monitor.py` | `pp_monitor.py`, `archive_monitor.py`; corresponding `test_*.py` |
| Pack membership and catalog intake | `patch_pack_intake.py` | `pack_intake.py`, `pack_catalog.py`; `test_pack_intake.py`, `test_pack_records.py`, `test_pack_catalog.py` |
| Preserve tracked series on startup | `patch_series_preservation.py` | `test_pack_intake.py` |
| Regular/annual identity and verified library presence | `patch_workflow.py` | `library_status.py`; workflow, queue-control and monitor tests |
| Activity, admission and DDL/NZB handoff | `patch_workflow.py` | `workflow.py`, `workflow_store.py`, `workflow_nzb.py`, `workflow_web.py`; corresponding `test_*.py`; one NZB fallback per exhausted single release, no-result remains Failed |
| Responsive queue interface | `patch_ddl_ui.py` | `ddl_queue.js`, `ddl_queue.css`, `test_ddl_ui.py` |
| Shared wide-screen layout | `patch_wide_layout.py` | `wide_layout.css` |
| SQLite write transactions | `patch_database_transactions.py` | `test_database_transactions.py` |
| Filename identity and single-volume recovery | `patch_file_matching.py` | `file_identity.py`, `test_file_identity.py`, `test_file_matching.py` |
| Explicit catalog volume labels | `patch_catalog_volumes.py` | `catalog_volume.py`, `test_catalog_volumes.py` |
| Story-arc search identities | `patch_story_arcs.py` | `story_arc_search.py`, `test_story_arc_search.py` |
| Wednesday release weeks | `patch_release_calendar.py` | `release_calendar.py`, `test_release_calendar.py` |

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

## Library metadata maintenance

`patch_library_metadata.py` follows converted-tagging installation and adds the idle
worker hook. `library_metadata.py` owns incremental catalog discovery and durable
repair admission. `metadata_repair.py` owns agreeing identity checks, provenance and
archive preservation. The explicit repair mode in `tagger_adapter.py` reuses v2
publication and recovery; normal archive/tagging paths remain strict. Settings live
in Activity and outcomes in the post-processing monitor. Focused coverage is in
`test_library_metadata.py` and `test_metadata_repair.py`.

Reader metadata supplements use `tagger_enrichment.py` and the explicit offline `tagger_supplement.py` preview/apply command. `test_tagger_enrichment.py` exercises real NFS publication, restored backups, preservation and a byte-stable repeat. The existing Modern service adds derived fields to future tags.
