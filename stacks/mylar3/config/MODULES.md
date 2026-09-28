# Custom Mylar modules

Adapters are named for the behavior they own. `apply_patches.py` is the ordered
build manifest; `verify_image.py` uses the same manifest against an isolated copy.
Adapters check expected native source and fail on drift. Runtime helpers live in
Mylar's package; adapters and tests stay in the build stage.

| Responsibility | Build adapter | Runtime helper / focused tests |
|---|---|---|
| Active DDL path and size handling | `patch_ddl_status.py` | `test_ddl_status.py` |
| HTTP response validation | `patch_ddl_responses.py` | `test_ddl_responses.py` |
| Exhausted mirrors | `patch_ddl_exhaustion.py` | `test_ddl_exhaustion.py` |
| Transient mirror lookup failures | `patch_ddl_mirror_retries.py` | `test_ddl_mirror_retries.py` |
| ComicTagger timeout | `patch_tagger_timeout.py` | `test_tagger_timeout.py` |
| Unnumbered issue parsing | `patch_unnumbered_issues.py` | `test_unnumbered_issues.py` |
| HTTP resume offsets | `patch_ddl_resume.py` | `test_ddl_resume.py` |
| Requeued download state | `patch_ddl_requeue.py` | `test_ddl_requeue.py` |
| Authenticated health/recovery API | `patch_diagnostics_api.py` | `worker_health.py`, `failed_downloads.py`, `cooldown_health.py`; `test_health.py`, `test_failed_downloads.py`, `test_cooldown_health.py` |
| Transfer lifecycle and queue recovery | `patch_queue_control.py` | `queue_control.py`, `verified_transfer.py`; corresponding `test_*.py` |
| DDL progress | `patch_queue_progress.py` | `queue_progress.py`, `test_queue_progress.py` |
| DDL release labels | `patch_queue_labels.py` | `test_queue_progress.py`; follows queue ordering, retains linked issue identity |
| Queue policy and execution ordering | `patch_ddl_schedule.py` | `ddl_schedule.py`, `test_queue_schedule.py` |
| Queue diagnostics and import problems | `patch_queue_views.py` | `import_problems.py`, `test_queue_views.py` |
| Cooldown search fallback | `patch_search_cooldown.py` | `test_search_cooldown.py`, `test_search_fallback.py` |
| Post-processing ownership and annual identity | `patch_postprocessing.py` | `processing_guard.py`, `test_pack_intake.py` |
| Post-processing observations | `patch_pp_monitor.py` | `pp_monitor.py`, `archive_monitor.py`; corresponding `test_*.py` |
| Pack membership and catalog intake | `patch_pack_intake.py` | `pack_intake.py`, `pack_catalog.py`; `test_pack_intake.py`, `test_pack_records.py`, `test_pack_catalog.py` |
| Preserve tracked series on startup | `patch_series_preservation.py` | `test_pack_intake.py` |
| Regular/annual identity and verified library presence | `patch_workflow.py` | `library_status.py`; workflow, queue-control and monitor tests |
| Activity, admission and DDL/NZB handoff | `patch_workflow.py` | `workflow.py`, `workflow_store.py`, `workflow_nzb.py`, `workflow_web.py`; corresponding `test_*.py` |
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
They are build-tested and not connected to native Mylar tagging. The isolated
`/opt/comictagger` runtime is copied into the image, while Mylar continues using its
vendored legacy tagger. Tests: `test_tagger_runtime.py`, `test_tagger_metadata.py`,
`test_tagger_archive.py`, `test_tagger_adapter.py`, `test_modern_tagger.py`. The archive helper writes only new
operation files, reopens them for verification and never replaces a source.
`fetch_tagger_sources.py` runs only during image construction.
The publisher owns atomic CBZ exchange and versioned recovery receipts. Conflict
copies remain private for review. All five helpers are retained under
`/opt/mylar3-fixes` in the final image, with no startup or native invocation.
Native routing, writer coordination, filesystem canaries and optional DDL discovery
remain separate activation gates.
