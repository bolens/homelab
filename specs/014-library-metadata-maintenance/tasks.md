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

- [ ] T008 Update affected stack contract documentation and module map; run focused and repository/image gates.
- [ ] T009 Merge reviewed changes, verify published GHCR image and mirror under RELEASING.md.
- [ ] T010 Perform verified Mylar-only deployment and opt-in canary, confirm library/catalog preservation, dependent-service uptime and UI, then remove operation backups. Record evidence in specs/014-library-metadata-maintenance/tasks.md.

## Dependencies and strategy

T002 precedes repair publication. US1 discovery and US2 reconciliation can be developed independently, then integrated before UI activation. Tests and documentation can be prepared alongside their owning module. Deliver all three stories together with both policies disabled until acceptance. No additional agents are needed for the resolved repository-local design.

## Implementation evidence

Focused archive, publication, discovery and conversion-queue tests passed. The isolated candidate image gate passed against the current pinned Mylar/Modern runtime. Two independent reviews covered behavior/contracts and preservation/recovery. Their unsupported-archive starvation and cached ownership findings were fixed with regressions. Later review refinements keep newest review outcomes visible and allow catalog ownership corrections to be rediscovered. Real power loss was not tested. Live acceptance and published-image proof remain pending.
