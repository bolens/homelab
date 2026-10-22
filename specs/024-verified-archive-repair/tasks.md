# Tasks: Verified archive repair

**Current delivery requirement (2026-10-10)**: Hosted CI must pass before any further merge. The user has revoked the outage waiver; historical waivers in the linked evidence history do not authorize new exceptions. Fix failing checks while preserving their acceptance assertions.

## Current remaining work

**Updated 2026-10-22.** 13 of 18 tasks are complete; 5 retain their full acceptance gates. T011/T013 repair adoption/history and T014 contract review are complete. Ordinary Mylar's current image data preservation is accepted; Komga stays running and the permanent worker stays inactive. Preparation and fixture proof remain separate from connected execution and live repair acceptance.

- **Producer integration:** the maintained active-input assembler and exact host-engine intent producer are implemented and independently reviewed; the historical source verification passes 1,306 controls across 73 suites under Python 3.10, with zero skips. The configured birth/session producers and forwarding entry already exist. Current-role capture, effective-scope production, SourceCohort and checked plan13 composition already exist. The engine intentionally refuses unbound create/start calls; do not widen that guard to make a fixture pass. The effective-scope observer's independently reviewed bootstrap join now derives the exact disposable reader mounts from originals, preserving production mount checks; source/compile and configured observation checks pass; fresh observations remain required for each owning attempt. Feature 023 T026/T029 and this feature's T012/T015 depend on the genuine producer/caller integration.
- **Existing source and runtime milestones:** creator/bootstrap, native catalog/processing observation, original-session reader task observation and plan13 role/library mapping are implemented. Published native/worker component proofs remain accepted for their recorded generations, and the ninth isolated bootstrap completes genuine queue imports, reader scan/progress and restart. These do not complete the connected installed factories, NFS or archive-terminal acceptance required by T012/T015. See [published component evidence](../023-verified-publication-corrections/evidence-history.md#published449-image-verification--2026-10-20) and [the current bootstrap record](../023-verified-publication-corrections/evidence-history.md#genuine-isolated-bootstrap-completed---2026-10-21).
- **T012/T015 connected acceptance:** finish genuine installed reader continuity, original Parent/Birth/provider custody, NFS preservation and archive prepare-to-execute-to-terminal production with factual native/worker consumption. Existing link/unlink protocol, phase receipts, reversal and checkpointed-WAL controls remain preserved. See [protocol evidence](evidence-history.md#prospective-nfs-publication-protocol--2026-10-20) and [WAL correction](evidence-history.md#checkpointed-reader-wal--2026-10-16).
- **T016/T017 live recovery:** retain verified backup/restore evidence and all four selected histories. Complete fresh configured repair, archive/owner/catalog/reader comparisons and restart acceptance. No selected import or ACK is accepted. Reader observations require fresh owning admission; their references expire after 120 seconds.
- **T018 and cleanup:** complete shared current-library acceptance before repaired-archive or bulk processing resumes. Preserve unresolved originals and the independently verified current backup. See [shared accepted preservation](../023-verified-publication-corrections/evidence-history.md#native405-data-preservation-accepted--2026-10-20) and the dependencies below.

PR #482 delivered the assembler correction with passing local and hosted checks.
A fresh batch passes the causal SourceFixture, source closure, owned-container
absence, current-role/protocol observations, active assembly and intent construction.
It enters the owning producer once, then fails without an accepted terminal return.
The primary refusal is `configured-overlay-exact-approved-edits`: the packet mapped
the operation to its host path instead of the installer-owned `/_operation`. The
source correction adds an early mapping check and fixes the separate actor/finalizer
descriptor double-close. All 1,406 controls across 75 suites and 14 outer controls
pass locally. A fresh H installation and independent verification of all 27 outputs
also pass without lifecycle changes. PR #485 delivered these corrections with all
required hosted checks passing. The corrected new packet and connected execution
remain required under feature 023 T026. Preserve the consumed generation and all
failed histories; no automatic replay, import ACK or bulk acceptance is granted.
See [the current owning boundary](../023-verified-publication-corrections/evidence-history.md#owning-producer-entry-after-assembler-delivery--2026-10-22).

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
- [ ] T012 [US3] Complete the isolated connected repair through `stacks/mylar3/config/reader_recovery/genuine_active_inputs.py` (`assemble`) and `genuine_plan13_producer.py` (`Producer.execute`), using the checked installation and current original cohort. Require actual installed Parent/Birth/stopped-reader/completed-preparation factories, same-mount NFS forward and explicit rollback phase evidence, independent archive/member/compressed-byte/page/metadata preservation, exact affected reader references and zero unrelated native/reader changes. Retain unknown outcomes without replay. Coordinate the feature 023 T026 owning-integration milestone and T029 runtime proof; local controls or an assembled plan alone do not complete this task.
- [x] T013 [US3] Integrate durable preparation/dispatch/acceptance/rollback history and native/worker recovery consumption in owning workflow/import modules; lost acknowledgements retain evidence, imports/cleanup wait for actual terminal acceptance, and no remote call runs under Writer.

## Phase 6: Delivery

- [x] T014 Update Mylar/Komga README and inspect their Compose, environment, metadata, preparation and ingress contracts together; diagnostics reuse existing settings/mounts/ports/privileges and introduce no new dependency. Regenerate affected catalog sources only through owning generators.
- [ ] T015 Close both delivery and configured-runtime evidence: independently review the final integrated source/failure boundaries, pass focused and owning source/runtime suites, `make validate`, `make ci-local` and all required hosted checks, then deliver through `RELEASING.md` with exact matching installed native/worker source/type proofs. Reuse unchanged accepted image proofs only for their exact original inputs. Complete the connected factory/NFS/terminal-consumption portion jointly with T012 and feature 023 T026/T029 when every criterion passes; source checks, publication or historical image proof alone are insufficient. No CI waiver or protection bypass is authorized.

## Phase 7: Scoped live acceptance

- [ ] T016 After T012 connected readiness and T015 matching-source/image delivery, coordinate the affected writers and validate or create a measured application-consistent backup with independently verified isolated restore for the exact live operation. Capture fresh affected archive/owner/catalog/reader state and actual image/process/configuration bindings; retain a compatible rollback image. Follow `stacks/mylar3/README.md` and `stacks/komga/README.md` for any necessary scoped rollout, normal Mylar startup and brief per-operation exclusion. Reuse an existing verified backup only while its original scopes/state still cover this operation; otherwise refresh through the owning backup route. Record private evidence digests without starting the experimental bulk worker.
- [ ] T017 [US3] With T016 backup/restore and fresh owning admission, execute the selected supported retained-original repair through the dedicated configured `archive-one` route in `stacks/mylar3/config/publication_archive_owned.py`, not the disposable fixture transition or generic import. Compare exact original/repaired members, pages, compressed bytes, metadata, native owner/catalog/census and affected reader records; require genuine terminal vectors and intended native/worker factual consumption. Preserve the four failed selected histories; reconcile a current DDL capture only from actual ordinary import and a fresh matching catalog-to-ACK event; prove guarded repeat handling without replay or manufactured historical ACKs. Record feature 022/023 joins and retain originals on uncertainty; do not release general writers prematurely.
- [ ] T018 [US3] After T017 scoped repair/import acceptance, verify restart reconciliation and the supported rollback/lost-response refusal evidence, then complete the protected current-library archive/owner/catalog/reader comparisons shared with feature 023 T018 before experimental bulk resumption. Feature 022 T024 separately supplies final post-bulk/idempotence acceptance. Record results in `specs/024-verified-archive-repair/tasks.md`; ordinary Mylar stays available under existing per-operation checks. Prune only conclusively accepted operation-owned copies after these gates, retaining one independently verified current backup, every unresolved original and durable failure history; do not treat a healthy service or successful Parent return as whole-library acceptance.

## Dependencies and execution

T001 → T002–T003 → US1 T004–T007 → US2 T008–T010 → US3 T011–T013 → T014–T015 reviewed source/image delivery → T016 verified live rollout → T017 scoped repair/import → T018 final acceptance/retention. US1 is independently deliverable; it does not complete US2/US3 or release features 022/023. IDs follow execution order. No production task is complete from earlier private experiments.

## Next execution and completion evidence

The assembler correction is delivered in PR #482. The fresh G run passed assembly
and entered the owning producer, but no terminal outcome was accepted. Its causal
SourceFixture passed with owned-container absence. The descriptor ownership and
early `/_operation` mapping checks pass 1,406 local controls and 14 outer checks.
The fresh H installation/export also verifies all 27 outputs without lifecycle changes.
Hosted delivery passes in PR #485. Bind those actual new originals into a corrected
packet with fresh source/observation bindings and exact isolated phase-log names. Existing observations and consumed
output directories cannot be reused. These facts do not complete the five open tasks.

1. **Finish static binding before freshness.** Preserve the original installation
   INNER/output27 and compatible selected-image/native180/SDK/worker evidence.
   Bind the actual used host module URIs/full9, scoped geometry, existing Writer
   protocol, query/protection inputs and reviewed finite operation request. Use the
   existing causal SourceFixture supplier for the exact effective-parent/readiness
   source pairs; do not relabel a prior cohort when those pairs change. SourceFixture
   and static staging precede the effective observer and `genuine_current_roles.run`;
   their original role/process/scope facts must still be within the owning 120-second
   window when consumed.
2. **Enter the existing connected path once.** `genuine_active_inputs.assemble`
   writes input originals only. Feed those originals to
   `genuine_plan13_producer.Producer.execute(activate=True)`, which rederives the
   checked installation and calls `comic_reader_lifecycle_parent.run_operation`.
   The owning Parent alone acquires/retains Writer, stops the isolated reader,
   verifies backup/restore, produces Birth/custody, runs `archive-one` and checks
   independent terminal vectors before its permitted reader resume. Retain the
   original preparation/execution/ACK/terminal/phase receipts and full preservation
   comparisons. No external wrapper or elapsed test count can supply these facts.
3. **Close milestones without a task cycle.** Feature 023 T022 checked installation
   and T026 owning integration are source/installation prerequisites, not a demand
   to finish all of T026 before entering shared runtime proof. One reviewed isolated
   batch may jointly close the configured portions of 023 T026/T029 and 024
   T012/T015 only when all their independent factory, selected-image, NFS,
   preservation and factual-consumption criteria pass. A partial batch leaves each
   unmet task unchecked; archive terminal/Parent completion still grants no live
   import ACK or general release.
4. **Then perform scoped live acceptance.** T016 validates applicable existing
   backup/restore evidence before creating anything new or rolling an image.
   T017 consumes a genuine retained malformed original; the causal malformed
   fixture transition is isolated-test-only. Require a fresh ordinary import ACK
   for the exact current event before reconciling retained history. T018 closes
   restart/current-library and later post-bulk retention gates. Unknown/partial
   operations preserve their evidence and are not retried automatically; actual
   rollback is invoked only through its supported owned route, never as a reset.

## Parallel opportunities

Bounded source proposals and independent preservation/failure reviews may run concurrently. Root alone owns tracked integration, generators, Git, image execution and live state. Shared module/API/census/reader contracts are sequential dependencies, so no unfinished task is labeled parallel.

## Implementation strategy

Retain delivered diagnostics and the implemented owning capability; finish their connected acceptance before live repair. Preserve all existing ordinary and nested boundaries. Continue the already authorized feature 023 negative-publication recovery in a separate source scope; both flows share final library, reader and writer-release acceptance.

## Evidence

T001–T010 accept the prospective design, diagnostics and bounded preparation.
T011/T013 accept adoption and durable-history implementation. Feature 023 T022's
published source/type/reliability milestone is accepted. T012/T015 still require
genuine connected factories and terminal consumption; T016–T018 require the
verified live rollout, repair/import and final preservation/retention checks.

The accepted PR #462 native capture and matching 27-output supplier remain
preserved. Current source verification and the successful ninth isolated
bootstrap are recorded in [the shared bootstrap
checkpoint](../023-verified-publication-corrections/evidence-history.md#genuine-isolated-bootstrap-completed---2026-10-21).
SourceCohort and connected acceptance remain open.

Docker address-pool exhaustion is resolved. The isolated new-directory NFS bind
passes with searchable ancestors and private leaves, and its exact resources
are removed. Full configured geometry/NFS/reader proof remains pending. Preserve
failed generations and the original 27 artifact references; see [the prerequisite
history](../023-verified-publication-corrections/evidence-history.md#disposable-nfs-bind-prerequisite-isolated--2026-10-21).

Detailed component tests, experiments and failure receipts remain in
[evidence history](evidence-history.md). Those records do not complete production
adoption or release the remaining feature 022/023 gates.

The ninth isolated batch completes both genuine Mylar queue imports, reader
scan/progress and restart; its worker stays stopped. PR #471 is merged after
passing hosted CI. This is bootstrap execution proof, with original data and
receipts retained; connected factories, NFS, publication, retained live-DDL and
fresh ACK acceptance remain open. See [the current bootstrap
record](../023-verified-publication-corrections/evidence-history.md#genuine-isolated-bootstrap-completed---2026-10-21).
