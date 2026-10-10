# Tasks: Verified comic release naming

**Input**: Design artifacts in `specs/022-comic-release-naming/`.
**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/naming.md` and `quickstart.md`.
**Organization**: Setup and foundations precede three independently testable user stories and final acceptance. Completed evidence is retained below; unchecked tasks require their full acceptance proof.
**Format**: Sequential `TNNN` IDs; `[US1]`–`[US3]` label story tasks. `[P]` is reserved for independent implementation in different files, with no incomplete dependencies.

**Current delivery requirement (2026-10-10)**: Hosted CI must pass before any further merge. The user has revoked the outage waiver; historical waivers in the linked evidence history do not authorize new exceptions. Fix failing checks while preserving their acceptance assertions.

## Current remaining work (2026-10-10)

T019/T023 remain open. Their combined naming/metadata and eligible bulk passes depend on feature 023's authenticated recovery, held rollout and current-library acceptance. The naming preference remains dot separators with a hyphen before the verified release group. The new native candidate, offline gate and target crypto fixture checks pass; those source/runtime checks do not accept the live library or authorize processing resumption. T024 remains open for the final idempotence, data and cleanup proof after the bulk pass. Additional reading-progress audit remains deferred.

## Phase 1: Setup

**Purpose**: Record preferences, preservation requirements and prospective contracts.

- [x] T001 Record user naming preferences and preservation criteria in `specs/022-comic-release-naming/spec.md`.
- [x] T002 Inspect pinned reader move/hash/progress contracts and document `specs/022-comic-release-naming/research.md`.
- [x] T003 Define data, API and rollback contracts in `specs/022-comic-release-naming/plan.md`, `specs/022-comic-release-naming/data-model.md`, `specs/022-comic-release-naming/contracts/naming.md` and `specs/022-comic-release-naming/quickstart.md`.

## Phase 2: Ownership and recovery foundations

**Purpose**: Establish guarded identity and durable recovery before any publication mutation.

- [x] T004 Add guarded native ownership/proposal resolution in `stacks/mylar3/config/release_naming.py`.
- [x] T005 Add no-overwrite native rename/catalog journal and recovery fencing in `stacks/mylar3/config/release_naming.py`, `stacks/mylar3/config/native_writers.py`, `stacks/mylar3/config/media_writer.py` and `stacks/komga/normalizer/media_writer.py`.
- [x] T006 Add primary-key versioned naming endpoints and image installation in `stacks/mylar3/config/patch_release_naming.py`, `stacks/mylar3/config/apply_patches.py` and `stacks/mylar3/config/verify_image.py`.
- [x] T007 Verify stale ownership, metadata contradictions, collisions, partial publication and catalog failure in `stacks/mylar3/config/test_release_naming.py` and `stacks/mylar3/config/test_media_writer.py`.

## Phase 3: US1 — Consistent normalized release names (P1)

**Goal**: Emit dotted release names with `-Group` and proven publication labels.
**Independent test**: Renderer/native-parser fixtures preserve annual, collected, fractional, variant, source/group and year identity; disabled-policy fixtures retain previous behavior.

- [x] T008 [US1] Implement one renderer, label preservation and disabled-by-default policy in `stacks/komga/normalizer/release_naming.py`.
- [x] T009 [US1] Add XXH3 source/reader hash checks, restore-verified temporary copies, bounded serial follow-up and asynchronous reader proof in `stacks/komga/normalizer/naming_worker.py`.
- [x] T010 [US1] Integrate naming after conversion/tagging in `stacks/komga/normalizer/normalize.py`, `stacks/komga/normalizer/writer_cycle.py` and `stacks/komga/normalizer/Dockerfile`.
- [x] T011 [US1] Verify renderer labels and native parser compatibility in `stacks/komga/normalizer/test_release_naming.py`, `stacks/mylar3/config/test_release_naming.py` and `stacks/mylar3/config/test_file_matching.py`.

## Phase 4: US2 — Recoverable library renaming (P1)

**Goal**: Reconcile interrupted moves without replay, lost payloads or false completion.
**Independent test**: Crash, acknowledgement, contention and reader-restoration fixtures retain originals and block new writers until exact recovery proof succeeds.

- [x] T012 [US2] Test native/worker crash boundaries, uncertain acknowledgements, writer contention and progress preservation in `stacks/mylar3/config/test_release_naming.py`, `stacks/komga/normalizer/test_naming_worker.py` and `stacks/komga/normalizer/test_writer_cycle.py`.
- [x] T013 [US2] Update disabled-policy examples and owning contracts in `stacks/komga/normalizer/normalizer.json.example`, `stacks/komga/prepare-normalizer.sh`, `stacks/komga/stack.yaml`, `stacks/komga/README.md`, `stacks/mylar3/config/MODULES.md` and `stacks/mylar3/README.md`; regenerate `documents/STACK-CATALOG.md` when affected.

## Phase 5: US3 — Auditable bulk pass (P2)

**Goal**: Apply only eligible publications in bounded combined rename/metadata batches, retaining held entries and compact proof.
**Independent test**: A reviewed manifest rejects stale sources/catalogs and ambiguous editions; a combined canary proves unchanged-hash reader restoration before metadata publication, followed by exact payload/native/reader proof and an idempotent second pass.

- [x] T014 [US3] Add read-only manifests, freshness checks, bounded apply/resume and idempotence tests in `stacks/komga/normalizer/naming_worker.py` and `stacks/komga/normalizer/test_naming_worker.py`.
- [x] T015 [US3] Complete focused/image/repository checks and independent review; deliver the reviewed change using `RELEASING.md` and record evidence in `specs/022-comic-release-naming/tasks.md`.
- [x] T016 [US3] Deploy compatible images using restore-verified backups, enable naming and prove one live rename following `stacks/komga/README.md` and `stacks/mylar3/README.md`; record acceptance in `specs/022-comic-release-naming/tasks.md`.
- [x] T017 [US3] Close unbracketed edition/collection identity gaps with regressions in `stacks/mylar3/config/release_naming.py`, `stacks/mylar3/config/test_release_naming.py`, `stacks/mylar3/config/file_identity.py`, `stacks/mylar3/config/test_file_identity.py` and `stacks/komga/normalizer/test_release_naming.py`; deliver and verify live repair before further bulk admission.
- [x] T018 [US3] Resolve falsely held missing filename years using exact metadata/catalog/link evidence in `stacks/mylar3/config/release_naming.py` and `stacks/mylar3/config/test_release_naming.py`; retain actual date/ID contradictions and prove final native parser compatibility.
- [ ] T019 [US3] Complete the bounded combined rename/metadata pass using `stacks/komga/normalizer/naming_worker.py` and the native shared-preservation entry point in `stacks/mylar3/config/tagger_supplement.py`; prove unchanged-hash reader restoration before metadata rewriting, final payload/ownership/readiness and cleanup, preserving exact-path credit deferrals.
- [x] T020 [US3] Deliver and verify the corrupt-ZIP fallback fix in `stacks/komga/normalizer/maintenance.py` and `stacks/komga/normalizer/test_maintenance.py`; prove bounded missing-end-record detection, retain dependency/unknown failures, and verify scoped preservation/native failure recovery under a completed bulk checkpoint. Persist guarded retry intent before volatile search submission in `stacks/mylar3/config/failed_downloads.py` with restart, queue-failure and ownership-drift regressions in `stacks/mylar3/config/test_failed_downloads.py` and actual native committed-cursor tests in `stacks/mylar3/config/test_database_transactions.py`; deliver the native image and reconcile the existing exact failed owner without replaying failure processing or search.
- [x] T021 [US3] Deliver and verify ComicInfo-preserving import confirmation in `stacks/komga/normalizer/maintenance.py`, `stacks/komga/normalizer/guided_match.py`, `stacks/komga/normalizer/test_maintenance.py` and `stacks/komga/normalizer/test_guided_match.py`; require exact ordered pages/all non-root-metadata extras, matching publication identity and both ZIP root metadata files, a verified retained original, stable hashes and truthful cleanup receipts, covering interruption/storage/link/mutation failures before live reconciliation.
- [x] T022 [US3] Preserve confirmed pack evidence through native naming and metadata publication in `stacks/mylar3/config/pack_bindings.py`, `stacks/mylar3/config/tagger_pack.py`, `stacks/mylar3/config/release_naming.py`, `stacks/mylar3/config/tagger_supplement.py`, `stacks/mylar3/config/tagger_native.py`, `stacks/mylar3/config/tagger_adapter.py`, `stacks/mylar3/config/workflow_store.py` and `stacks/mylar3/config/patch_pack_intake.py`; capture durable exact-owner/path/hash transitions before mutation, atomically rebind all matching confirmed members before fence clearance, preserve sidecars/history and reject stale or foreign evidence. Add rename, metadata, interruption, multi-pack, replay and ownership/content regressions in `stacks/mylar3/config/test_pack_bindings.py`, `stacks/mylar3/config/test_release_naming.py` and `stacks/mylar3/config/test_pack_records.py`; complete independent review, image/repository gates and verified rollout before resuming bulk.
- [ ] T023 [US3] Correct numeric-title padded parsing, explicit print run/four-digit issue/publication-year fields and redundant verified `#issue` blocks in `stacks/mylar3/config/release_naming.py`, `stacks/mylar3/config/patch_release_naming.py` and `stacks/komga/normalizer/release_naming.py`, with actual native parser/renderer regressions; add explicit predecessor-bound version-2 recovery in the native API and worker with retained-copy/reader/ownership/failure regressions, deliver matching images and reconcile rejected entries through exact retained receipts before final acceptance. Finish eligible bulk entries under coordination using `stacks/komga/normalizer/naming_worker.py`; record archive/native/reader acceptance and every held entry in `specs/022-comic-release-naming/tasks.md`, refresh the supplement preview and apply proven metadata-only corrections to canonical/later-intake archives excluded from the frozen combined candidates, and rebind repaired-file credit deferrals through verified old-to-new receipts before the supplement pass resumes. The user deferred an additional reading-progress audit; retain existing safeguards.

## Phase 6: Final acceptance and cleanup

- [ ] T024 Remove only conclusively completed temporary preservation/restore copies, verify second-pass idempotence and service/data acceptance, and publish final evidence in `specs/022-comic-release-naming/tasks.md` and `specs/022-comic-release-naming/quickstart.md`.

## Dependencies and execution

Setup T001–T003 → foundations T004–T007 → US1 T008–T011 → US2 T012–T013 → US3 T014–T023 → final acceptance T024. T015 review/delivery and T016 verified rollout precede live bulk admission. T017–T018 identity corrections are verified. T019 began with a verified combined canary and remains open until the entire eligible pass finishes. The worker portions of live-discovered T020–T021 passed before resumed T019/T023 admission at the 559-publication checkpoint. T020–T021 are accepted; the additional native retry-durability rollout passed at the completed 772-publication checkpoint before further combined admission. T022 passed reviewed delivery, verified native rollout and the Grimm pack canary at 931 completed publications before further T019/T023 admission. Resumed T019/T023 and T024 also require spec 023 T009–T016 enforcement/image/delivery gates and T017/T018 coordinated current-library acceptance. T024 depends on T019–T023 acceptance; interrupted or uncertain copies remain retained.

Task IDs now follow execution order. Earlier appended-task references were updated consistently in the retained evidence: former T019→T017, T021→T018, T020→T019, T022→T020, T023→T021, T017→T022 and T018→T023. This ordering correction preserves completed history and does not claim these later corrections were planned before discovery.

## Parallel opportunities

- US1: isolated renderer fixtures and native parser fixtures can run independently after T008–T010; they have separate temporary data.
- US2: native journal and worker acknowledgement/fence tests can run independently after their implementation is frozen.
- US3: read-only contract review and isolated failure-path review can run independently against one fixed candidate after T014 or a discovered repair. Live archive, catalog, reader and Git writes stay serialized under the designated coordinator.

No implementation task is marked `[P]`: the remaining tasks depend on the same coordinated media state or delivery gates. The user authorized parallel implementation through bounded units in separate worktrees. Each unit has one source owner and frozen dependency handoffs; shared manifests, contracts, generators, Git and live state retain one integration owner. Independent final review is required for substantive PRs.

## Implementation strategy

Deliver US1 as the opt-in naming MVP, verify US2 recovery gates, then roll out US3 with backups, one canary and bounded serial batches. Pause at completed checkpoints for newly discovered repairs, reconcile accepted operations before new admission, and finish with idempotence and cleanup proof. Mark completion only after the stated acceptance evidence succeeds.

## Current evidence

Naming foundations and earlier live canaries are accepted as recorded by T001–T018 and T020–T022. The interrupted combined/bulk pass, supplement reconciliation and final idempotence remain open under T019/T023/T024. Current verification and release dependencies are listed above.

Detailed dated checks, previous delivery exceptions, image identities and failure receipts are retained in [evidence history](evidence-history.md). Those historical observations do not override the current hosted-CI requirement or complete live acceptance.
