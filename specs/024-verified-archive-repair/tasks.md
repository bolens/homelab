# Tasks: Verified archive repair

**Current delivery requirement (2026-10-10)**: Hosted CI must pass before any further merge. The user has revoked the outage waiver; historical waivers in the linked evidence history do not authorize new exceptions. Fix failing checks while preserving their acceptance assertions.

## Current remaining work

**Updated 2026-10-20.** T011/T013 repair adoption/history and T014 contract review are complete. Ordinary Mylar's current image data preservation is accepted; Komga stays running and the permanent worker stays inactive. Preparation and fixture proof remain separate from connected execution and live repair acceptance.

- **Producer integration:** the maintained active-input assembler and exact host-engine intent producer are implemented and independently reviewed; combined source verification passes 1,219 controls across 72 suites under Python 3.10, with zero skips. The configured birth/session producers and forwarding entry already exist. Current-role capture, effective-scope production, SourceCohort and checked plan13 composition already exist. The engine intentionally refuses unbound create/start calls; do not widen that guard to make a fixture pass. The effective-scope observer's independently reviewed bootstrap join now derives the exact disposable reader mounts from originals, preserving production mount checks; source/compile checks pass, with configured observation still pending. Feature 023 T026/T029 and this feature's T012/T015 depend on the genuine producer/caller integration.
- **Existing source milestones:** creator/bootstrap, native catalog/processing observation, original-session reader task observation and plan13 role/library mapping are implemented. The SourceCohort producer's integrated recovery inventory passes 1,219 controls across 72 suites without skips. These are source/component milestones, with actual selected-image execution still required. See [producer evidence](evidence-history.md#causal-source-cohort-producer--2026-10-20), [plan composition](evidence-history.md#checked-plan13-original-reference-composition--2026-10-20) and [task observation](evidence-history.md#original-reader-task-observation-source--2026-10-20).
- **T012/T015 connected acceptance:** finish genuine installed reader continuity, original Parent/Birth/provider custody, NFS preservation and archive prepare-to-execute-to-terminal production with factual native/worker consumption. Existing link/unlink protocol, phase receipts, reversal and checkpointed-WAL controls remain preserved. See [protocol evidence](evidence-history.md#prospective-nfs-publication-protocol--2026-10-20) and [WAL correction](evidence-history.md#checkpointed-reader-wal--2026-10-16).
- **T016/T017 live recovery:** retain verified backup/restore evidence and all four selected histories. Complete fresh configured repair, archive/owner/catalog/reader comparisons and restart acceptance. No selected import or ACK is accepted. Reader observations require fresh owning admission; their references expire after 120 seconds.
- **T018 and cleanup:** complete shared current-library acceptance before repaired-archive or bulk processing resumes. Preserve unresolved originals and the independently verified current backup. See [shared accepted preservation](../023-verified-publication-corrections/evidence-history.md#native405-data-preservation-accepted--2026-10-20) and the dependencies below.

## Phase 1: Setup

- [x] T001 Complete independent prospective design and preservation review of `specs/024-verified-archive-repair/spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/archive-repair.md` and `quickstart.md`; keep private preliminary proof separate from production acceptance.

## Phase 2: Shared bounded foundations

- [x] T002 Integrate checked pure ZIP layout, derivation and repair classification in `stacks/mylar3/config/publication_archive_layout.py`, `publication_archive_derivative.py` and `publication_archive_repair.py`; prove full CRC/member/page/root-metadata/compressed-byte preservation and held unsupported input in owning tests.
- [x] T003 Generate byte-identical pure worker modules through `scripts/sync-publication-reader.py`, recording provenance separately so generated headers cannot invalidate embedded source hashes; verify complete generated parity and existing guard tests.

## Phase 3: US1 — Observable retained diagnostics (P1)

Goal: explain supported structural repairs, compatibility, conversion and retained review without changing admission.

Independent test: valid ordinary archives bypass diagnosis; failed source inventory retains its terminal outcome and exposes only fixed public codes.

- [x] T004 [US1] Implement stable bounded source diagnosis in `stacks/mylar3/config/publication_archive_diagnostics.py` and `test_publication_archive_diagnostics.py`; bind canonical parents/full source signature/SHA/deadline and refuse late byte/mode/inode/alias changes without private output.
- [x] T005 [US1] Integrate direct ordinary-inventory refusal in `stacks/mylar3/config/publication_native.py` and `stacks/komga/normalizer/publication_guard.py`, with owning `test_publication_archive_admission.py` suites; registry/catalog/owner failures cannot classify and diagnostic failures cannot escape terminal refusal.
- [x] T006 [US1] Carry sanitized diagnostic codes through actual retained processing/history and worker reporting in `stacks/mylar3/config/processing_guard.py`, `pp_monitor.py` and the owning normalizer caller, with observable tests; preserve retained status and omit paths, hashes, metadata and payloads.
- [x] T007 [US1] Install modules and verify imports/tests in `stacks/mylar3/config/patch_publication_guard.py`, `verify_image.py`, `workflow.py`, `MODULES.md` and `stacks/komga/normalizer/Dockerfile`; advertise diagnostic readiness separately from unimplemented adoption.

## Phase 4: US2 — Non-executable owned preparation (P1)

Goal: independently verified private repaired bytes and original custody bound to actual native ownership.

Independent test: exact supported preparation succeeds without library/catalog mutation; source/custody/catalog/census drift and uncertainty remain held.

- [x] T008 [US2] Implement trusted exceptional witness production and immutable preparation in `stacks/mylar3/config/publication_archive_owned.py` and owning tests; bind existing Controller/Writer, exact source, complete catalog/census and current allowed/rejected owner policy without ordinary-reader exceptions outside this source.
- [x] T009 [US2] Implement exclusive private derivative/custody creation, fsync/readback and preservation sealing in `publication_archive_owned.py`; prove 512 MiB source and existing member/expanded/metadata/deadline limits, physical aliases, late changes and interrupted preparation.
- [x] T010 [US2] Add authenticated primary-key preparation/status integration in `stacks/mylar3/config/publication_api.py` and owning tests; confined exact inputs, immutable token and false execution/adoption grants remain explicit.

## Phase 5: US3 — Owned publication and recovery (P2)

Goal: adopt the exact repaired bytes through current correction/native/reader policy, with recoverable original custody.

Independent test: one isolated owned repair completes with matching reader/native state; rejected owners, mixed phases and lost responses cannot publish or replay.

- [x] T011 [US3] Implement the dedicated same-payload native repair capability in `publication_archive_owned.py`, `publication_native.py` and `publication_api.py`; prove fresh complete owner/census/catalog/source/stage/custody checks without widening nested lineage, ordinary `require` or generic import.
- [ ] T012 [US3] Integrate exact reader continuity, finite phase/CAS and filesystem preservation/rollback in the owning native and normalizer processing boundaries; test complete affected book/page reference preservation and zero unrelated row/member changes. Depend on feature 023 T022/T026 checked lifecycle parent/provider and current installed cohort.
- [x] T013 [US3] Integrate durable preparation/dispatch/acceptance/rollback history and native/worker recovery consumption in owning workflow/import modules; lost acknowledgements retain evidence, imports/cleanup wait for actual terminal acceptance, and no remote call runs under Writer.

## Phase 6: Delivery

- [x] T014 Update Mylar/Komga README and inspect their Compose, environment, metadata, preparation and ingress contracts together; diagnostics reuse existing settings/mounts/ports/privileges and introduce no new dependency. Regenerate affected catalog sources only through owning generators.
- [ ] T015 Complete independent integrated failure review, actual selected-native/worker source-image tests, focused checks, `make validate` and `make ci-local`; deliver reviewed source through `RELEASING.md` and record source/image proof in this file. All required hosted checks and local checks must pass on the reviewed final head; no CI waiver or branch-protection bypass is authorized. Feature 023 T022/T026 owning lifecycle/code/installation gates are prerequisites; historical image proof does not accept this new cohort.

## Phase 7: Scoped live acceptance

- [ ] T016 Coordinate writers, capture fresh affected-state/reader/native baselines, measure and create consistent backup plus independently verified restore, then deploy compatible matching images following owning READMEs using brief affected-operation writer windows and normal Mylar startup; record exact actual image/process and private evidence digests in this file.
- [ ] T017 [US3] Execute the supported retained-original repair through its dedicated owning route, verify actual archive/owner/catalog/reader state and guarded repeat handling, and reconcile DDL only through actual ordinary import acknowledgement; update feature 022/023 acceptance evidence without claiming general writer release prematurely.
- [ ] T018 [US3] Verify restart, rollback/lost-response refusal and complete current-library acceptance; reference feature 023 T018 shared current-library acceptance before experimental bulk resumption and feature 022 T024 final post-bulk acceptance. Ordinary Mylar remains available under its existing per-operation checks; prune only conclusively superseded operation-owned copies while retaining one independently verified current backup and unresolved originals.

## Dependencies and execution

T001 → T002–T003 → US1 T004–T007 → US2 T008–T010 → US3 T011–T013 → T014–T015 reviewed source/image delivery → T016 verified live rollout → T017 scoped repair/import → T018 final acceptance/retention. US1 is independently deliverable; it does not complete US2/US3 or release features 022/023. IDs follow execution order. No production task is complete from earlier private experiments.

## Parallel opportunities

Bounded source proposals and independent preservation/failure reviews may run concurrently. Root alone owns tracked integration, generators, Git, image execution and live state. Shared module/API/census/reader contracts are sequential dependencies, so no unfinished task is labeled parallel.

## Implementation strategy

Deliver truthful diagnostics first while implementing the separate owning capability. Preserve all existing ordinary and nested boundaries. Continue the already authorized feature 023 negative-publication recovery in a separate source scope; both flows share final library, reader and writer-release acceptance.

## Evidence

T001–T010 accept the prospective design, retained diagnostics and bounded non-executable preparation. T011 and T013 accept dedicated adoption and durable recovery-history implementation. Installed reader continuity, integrated acceptance and live repair remain open under T012 and T015–T018. Current verification and remaining release dependencies are listed above.

Detailed dated source/image tests, retained-original experiments and failure receipts are retained in [evidence history](evidence-history.md). Private repaired copies and earlier component proofs do not complete production adoption or authorize hold release.

Earlier candidate and installer checks remain in [this feature's history](evidence-history.md#installed-recovery-prerequisite-2026-10-11) and the [shared recovery checkpoint](../023-verified-publication-corrections/evidence-history.md#merged-recovery-and-configured-installer-follow-up-2026-10-15). The current PR #383 worker passes 254 installed cases plus two permission-fault cases on exact private copies. After correcting the test export permissions, current native source parity, installed reader types and the complete reliability gate pass without skips. T012/T015 remain open because feature 023 T026 still needs genuine connected owning factory proof. These component results do not supply configured repair or live acceptance. See [current worker evidence](../023-verified-publication-corrections/evidence-history.md#current-worker-implementation-verification--2026-10-18).

Feature 023 T022 is now complete: the published native image passes source parity, installed reader types and the complete reliability gate without skips. This satisfies the portable owning-phase/checked-installation milestone. T012/T015 remain open because their separate T026 genuine connected-factory prerequisite is not yet proved.

PR #449 delivers the shared active-input, host-engine and disposable-scope sources with passing CI and isolated candidate gates. The genuine connected factory/NFS/terminal prerequisites for T012/T015 remain unproved; see [shared delivery evidence](../023-verified-publication-corrections/evidence-history.md#integrated-recovery-sources-delivered--2026-10-20). No repair, adoption or live import follows from this source delivery.

The matching configured reader-parent artifact staging now passes with 27 retained original references. The disposable bootstrap stops before container creation because Docker cannot allocate another default network. T012/T015 still require the genuine connected factory/NFS/terminal proof; see the [shared prerequisite evidence](../023-verified-publication-corrections/evidence-history.md#disposable-reader-parent-staging-and-network-prerequisite--2026-10-21).

The default-network exhaustion is resolved. Disposable bootstrap now isolates a daemon/NFS traversal prerequisite; the limited empty-directory bind alternative passes without live-library permission changes. Full geometry, connected factory and terminal acceptance remain pending; see the [shared prerequisite follow-up](../023-verified-publication-corrections/evidence-history.md#disposable-nfs-bind-prerequisite-isolated--2026-10-21).

The shared coupled source/consumer correction passes the full 1,239-control gate with closed source custody. T012/T015 remain open for the changed native image and connected factory/terminal proof; [shared source evidence](../023-verified-publication-corrections/evidence-history.md#coupled-disposable-recovery-source-verified--2026-10-21).

The initial PR #461 source result confused daemon Python 3.10 with Modern
tagger Python 3.13. The corrected predicate and two stale manifests now pass
owning regressions, the complete 1,239-control source gate and local validation.
Required hosted image CI and fresh installed/configured acceptance remain
pending. Existing open acceptance tasks remain open. See [the correction record](../023-verified-publication-corrections/evidence-history.md#hosted-ci-closure-and-interpreter-correction--2026-10-21).
