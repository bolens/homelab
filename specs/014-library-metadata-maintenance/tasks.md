# Tasks: Automatic library metadata maintenance

## Setup and foundation

- [x] T001 Record boundaries and acceptance in specs/014-library-metadata-maintenance/spec.md and plan.md.
- [x] T002 Add explicit bounded nested inspection and recovery-compatible repair staging in stacks/mylar3/config/tagger_archive.py and tagger_adapter.py.

## US1: Missing tags

- [x] T003 [US1] Add incremental exact-catalog discovery and durable deduplication in stacks/mylar3/config/library_metadata.py with test_library_metadata.py fixtures.

## US2: Nested copies

- [x] T004 [US2] Implement identity checks, root-preserving XML merge, provenance and full archive verification in stacks/mylar3/config/metadata_repair.py with test_metadata_repair.py interruption/preservation cases.
- [x] T005 [US2] Connect durable repair admission, existing publisher recovery and worker priority in stacks/mylar3/config/library_metadata.py.

## US3: Operator controls

- [x] T006 [US3] Add independent settings and maintenance status in stacks/mylar3/config/workflow.py, workflow.html, pp_monitor.py and post_processing.html.
- [x] T007 [US3] Install modules and native idle hook through stacks/mylar3/config/patch_library_metadata.py and apply_patches.py; verify idempotence.

## Delivery and acceptance

- [x] T008 Update affected stack contract documentation and module map; run focused and repository/image gates.
- [x] T009 Merge reviewed changes, verify published GHCR image and mirror under RELEASING.md.
- [x] T010 Perform verified Mylar-only deployment and opt-in canary, confirm library/catalog preservation, dependent-service uptime and UI, then remove operation backups. Record evidence in specs/014-library-metadata-maintenance/tasks.md.

## Dependencies and strategy

T002 precedes repair publication. US1 discovery and US2 reconciliation can be developed independently, then integrated before UI activation. Tests and documentation can be prepared alongside their owning module. Deliver all three stories together with both policies disabled until acceptance. No additional agents are needed for the resolved repository-local design.

## Implementation evidence

Focused archive, publication, discovery and conversion-queue tests passed. The isolated candidate image gate passed against the current pinned Mylar/Modern runtime. Two independent reviews covered behavior/contracts and preservation/recovery. Their unsupported-archive starvation and cached ownership findings were fixed with regressions. Later review refinements keep newest review outcomes visible and allow catalog ownership corrections to be rediscovered. Real power loss was not tested. Published-image and live acceptance are recorded below.

PR #161 merged as `4d97471240490e98dd18008fafd81444068a0cd4`. All PR and merged-commit validation, security, source-lint, image-publication and Pages workflows passed. Mylar deployment passed application backup/isolated restore and initial catalog/library preservation checks. Final live activation passed as recorded below.

The published image digest is `sha256:59770fbca4c1e5db49610a80490bf69d7cd90f1ba71136e285744d80a6d453a1`. Its installed-image gate passed. Both library policies are enabled and persisted through the authenticated Activity UI. A real idle scan started. NFS repair/recovery canaries preserved every member and supported attribute. Browser checks passed at 390, 1440 and 2560 pixels with no overflow or console/request errors. Screenshots were inspected.

Final preservation retained all baseline catalog IDs and library files, allowing exactly one independently verified concurrent normalizer conversion. The retained original, prepared CBZ, committed tagging journal and final tagged archive proved identical page/extra payloads and preserved attributes. All other baseline files remained unchanged. Database integrity passed. Mylar is healthy, its prior DDL pause policy was restored, and Komga, NZBGet, the normalizer and Uptime Kuma retained their container IDs and start times. Temporary application backup and isolated restore copies were removed after verification. Existing normalizer recovery retention remains intact. No full-library backup or real power-loss test was performed.
