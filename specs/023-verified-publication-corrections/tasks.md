# Tasks: Verified publication corrections

**Input**: `spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/publication-corrections.md` and `quickstart.md`.
**Organization**: Setup → payload/state foundations → reviewed registration → all guarded publication paths → operational repeat reconciliation → final acceptance.
**Format**: Sequential `TNNN`; `[US1]`–`[US3]` identify user-story tasks. Shared writers and delivery stay serialized. No live task is complete under the current privileged-access hold.

## Phase 1: Setup

- [x] T001 Validate prospective requirements, researched source boundaries and complete contracts in `specs/023-verified-publication-corrections/spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/publication-corrections.md` and `quickstart.md`; complete independent design review before implementation.

## Phase 2: Payload and state foundations

- [x] T002 Implement bounded metadata-independent inventories and exact regular-member/page-order vectors in `stacks/mylar3/config/publication_guard.py` and `stacks/mylar3/config/test_publication_guard.py`; bundle the existing pinned offline archive verifier and libarchive dependency in `stacks/mylar3/Dockerfile`, proving actual ZIP/RAR/7z runtime support and held unsupported/unstable input.
- [ ] T003 Implement immutable correction attestations, complete census/revision and explicit reviewed epoch initialization and prepared-marker/SQLite/final-marker missing-state binding/recovery in `stacks/mylar3/config/publication_guard.py`, `stacks/mylar3/config/native_writers.py` and `stacks/mylar3/config/workflow_store.py`; prove crash, loss, corruption, full-record coverage, contradictory owners and restart controls in `stacks/mylar3/config/test_publication_guard.py`.

## Phase 3: US1 — Reviewed correction registration (P1)

**Goal**: Persist only explicitly reviewed payload/owner evidence.
**Independent test**: Registration verifies the current exact correct owner/archive, rejects stale/unreviewed inputs and safely reconciles identical replay; retagging/recompression yields the same payload identity.

- [ ] T004 [US1] Add bounded prepare/commit registration, path-confined primary-key advisory checks and exact intent/census replay in `stacks/mylar3/config/publication_guard.py` and `stacks/mylar3/config/patch_publication_guard.py`; verify restricted-key denial, evidence/owner ambiguity, scope, protocol and lock order in `stacks/mylar3/config/test_publication_guard.py`.
- [ ] T005 [US1] Install and verify the focused adapter/helper at the required manifest point in `stacks/mylar3/config/apply_patches.py`, `stacks/mylar3/config/verify_image.py` and `stacks/mylar3/config/MODULES.md`; prove repeat patching and actual image imports without source-layout assumptions.

## Phase 4: US2 — Hold conflicts before publication (P1)

**Goal**: Every native and worker mutation respects verified correction evidence.
**Independent test**: Known wrong payloads remain retained with no tags, placement, owner/status mutation, submit, false completion or cleanup; genuinely different eligible payloads continue.

- [ ] T006 [US2] Guard ordinary, annual, storyarc and oneoff native postprocessing before scripts/tagging/duplicate handling and before placement/status commits in `stacks/mylar3/config/patch_publication_guard.py` and `stacks/mylar3/config/processing_guard.py`; verify terminal retained-review across disabled/Legacy/Modern tagging and source-changing scripts in `stacks/mylar3/config/test_publication_guard.py`.
- [ ] T007 [US2] Guard manual/backend tagging and converted follow-up in `stacks/mylar3/config/tagger_backend.py`, `tagger_native.py`, `tagger_service.py` and `converted_tagging.py`; extend their owning `test_*.py` suites to prove conflict and unavailable-state retention before publication and replay.
- [ ] T008 [US2] Guard rescans and converted catalog ownership repair before row changes in `stacks/mylar3/config/file_identity.py`, `stacks/mylar3/config/converted_catalog.py` and `patch_media_writers.py` (actual manualRename/downloadLocal/moveit.movefiles/helpers.file_ops/librarysync.libraryScan branches); extend `test_file_identity.py`, `test_file_matching.py` and `test_converted_catalog.py` for annual shadows, exact rejected payloads and no row deletion/reassignment.
- [ ] T009 [US2] Guard native naming, metadata supplementation and recovery/acknowledgement before source or catalog mutation in `stacks/mylar3/config/release_naming.py`, `stacks/mylar3/config/tagger_supplement.py`, `library_metadata.py`, `tagger_adapter.py` and `tagger_nfs.py` (including direct repair_nested publication, replay and reviewed derivative aliases) and their owning `test_*.py` suites; retain journal/fence/lineage contracts and block stale or conflicting proof.
- [ ] T010 [US2] Implement worker advisory/version/complete-census-marker/source and fresh matched correct-owner binding and independent portable vectors in `stacks/komga/normalizer/publication_guard.py` and `stacks/komga/normalizer/test_publication_guard.py`; require native final enforcement, fresh all-row correct-owner/archive evidence under the shared writer for worker-only mutations, and avoid remote API calls under that writer. Map this into `writer_cycle.py`/`test_writer_cycle.py`: its complete conversion and maintenance cycle holds the writer, so use pre-lock immutable batch advisories or full local authority validation inside the lock. Test same-revision owner/path/content drift and missing attestations.
- [ ] T011 [US2] Guard common/guided/pack import submission, existing-target confirmation, Extras placement and duplicate cleanup in `stacks/komga/normalizer/import_recovery.py`, `pack_recovery.py` and `maintenance.py`; extend their owning `test_*.py` suites to prove no submit/report/delete or prior-proof replacement on conflict.
- [ ] T012 [US2] Guard conversion publication, reader/catalog notifications and naming/metadata preparation/recovery in `stacks/komga/normalizer/normalize.py` and `naming_worker.py`; extend `test_normalize.py` and `test_naming_worker.py` for old-to-new payload binding, changed registry/source and no publication on uncertainty.

## Phase 5: US3 — Retained repeat reconciliation (P2)

**Goal**: Repair exact existing repeats while preserving correct publications and legitimate wanted intent.
**Independent test**: A reviewed scoped repair verifies isolated restores, preserves the correct archive/owner/reader, retains the repeat outside the library and changes only proved false catalog claims.

- [ ] T013 [US3] Document and validate the bounded registration importer and repeat-repair contract in `specs/023-verified-publication-corrections/contracts/publication-corrections.md`, `quickstart.md` and `stacks/mylar3/README.md`; private operational plans must bind actual evidence/current files and must not fabricate release provenance or overwrite the correct publication.
- [ ] T014 [US3] Prepare exact private registration/reconciliation intents and verify their stale-owner/source/backup refusal controls in isolated fixtures; bind the scoped plan to `specs/023-verified-publication-corrections/contracts/publication-corrections.md` and record readiness/gaps in `specs/023-verified-publication-corrections/tasks.md` without publishing private payloads or executing live mutation.

## Phase 6: Delivery and final acceptance

- [ ] T015 Update affected stack contracts together in `stacks/mylar3/docker-compose.yml`, `stack.env.example`, `stack.yaml`, `prepare-stack.sh`, `caddy_snippet.conf.example` and `README.md`, plus the matching `stacks/komga/` examples/preparation/metadata/README; document private-state backups and compatible guard protocol without adding mounts, ports or privileges. Regenerate `documents/STACK-CATALOG.md` and other generated surfaces only from affected sources.
- [ ] T016 Complete independent contract/failure review, focused/native-image/worker-image checks and `make ci-local`; deliver reviewed source through `RELEASING.md` and verify matching image publication, GitHub/local/Gitea synchronization and open PR disposition. Record evidence in `specs/023-verified-publication-corrections/tasks.md`. This precedes T017 live rollout.

## Phase 7: US3 — Live acceptance and scoped cleanup

- [ ] T017 [US3] Once privileged access is permitted, coordinate writers and execute scoped consistent backup/isolated restore, matching-image native-first rollout, exact reviewed registration and retained-repeat repair following `stacks/mylar3/README.md` and `stacks/komga/README.md`; record archive/owner/reader/database acceptance in `specs/023-verified-publication-corrections/tasks.md`.
- [ ] T018 [US3] Verify live known-conflict and legitimate different-payload canaries plus restart/retention/data acceptance in `specs/023-verified-publication-corrections/tasks.md` and `quickstart.md`; release writer holds only after protected complete current-library acceptance.
- [ ] T019 [US3] Remove only conclusively accepted operation-owned temporary preservation/restore copies and update related `specs/022-comic-release-naming/tasks.md` acceptance; preserve prior backups, correction/quarantine evidence and unresolved originals.

## Dependencies and execution

T001 → T002–T003 → T004–T005 → T006–T012 → T013–T015 → T016 reviewed delivery → T017 verified live rollout/reconciliation → T018 → T019. Task IDs follow execution order and delivery precedes live application. T017–T019 remain paused by the user’s no-privileged-access restriction.

## Parallel opportunities

Independent design/contract and failure-path reviews can inspect a frozen candidate concurrently. Native and worker isolated fixture checks can run separately. Shared source integration, Git, generators, registry admission and all live media/catalog writers stay under one coordinator; no unfinished implementation is marked `[P]`.

## Implementation strategy

Build the immutable reviewed-registration MVP first, then prove every publication boundary before claiming prevention. Keep existing-repeat repair separate from detection. Continue source/isolated/CI work while the user is away; preserve the operational hold and record all acceptance gaps honestly.

## Evidence

- Baseline PR #223 at `d0120332b5529e2f9d3c751a2e5ffce48b4945f6` fixes pack capture generations and aggregate evidence, not actual publication identity. Both image publications and all PR/main gates pass; runtime deployment remains held.
- Read-only evidence shows five newly present Heavy Metal files repeat already corrected 1977 payloads under a newer-series claim. Current file/native path ownership and acquisition provenance require protected verification; the observed snatches are not an exact release-to-file chain. Existing correct files and private historical repair evidence remain retained.
- T001: independent contract and failure reviews closed bootstrap/crash ordering, canonical page-token semantics and worker same-revision owner drift. Native-held-first rollout order and concrete legacy/manual/replay/writer-cycle boundaries are assigned. All 13 functional requirements and four success criteria map to ordered tasks; the 10-item spec-quality checklist passes. The payload foundation is recorded separately in T002; no registration, repeat relocation, rollout or final acceptance is claimed.

- T002 completed: isolated payload foundation has 17 passing controls without skips, including independently fixed payload vectors, authored RAR4/RAR5/7z payloads and corruption, ZIP directory-type disagreement, complete plain-TAR termination, held compressed wrappers, bounded source hashing and child output/timeouts. Peer findings on directory indicators, growing sources and compressed trailers were corrected. Both independent delta reviews are clear and staged `make ci-local` passes, including all repository checks and history secret scanning. The actual pinned native-image build gate passed all 17 payload controls without skips at source `3abbe7d` (PR #224, build job `111486330407`); the complete isolated Mylar image gate passed. A separate upstream-source selector failure was corrected by preserving the first native `FROM`; all checks on the corrected delivery head remain required before merge. No registry or publication-path integration is claimed.
