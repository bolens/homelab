# Tasks: Verified publication corrections

**Input**: `spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/publication-corrections.md` and `quickstart.md`.
**Organization**: Setup → payload/state foundations → reviewed registration → all guarded publication paths → operational repeat reconciliation → final acceptance.
**Format**: Sequential `TNNN`; `[US1]`–`[US3]` identify user-story tasks. Shared writers and delivery stay serialized. Privileged access was restored on 2026-10-04; live tasks still require their source, backup and acceptance prerequisites.

**Current delivery requirement (2026-10-10)**: Hosted CI must pass before any further merge. The user has revoked the outage waiver; historical waivers in the linked evidence history do not authorize new exceptions. Fix failing checks while preserving their acceptance assertions.

## Current acceptance work

**Updated 2026-10-22.** 25 of 33 tasks are complete; eight retain their full integration or operational acceptance gates. The accepted ordinary Mylar baseline is the PR #405 image. Its complete original-bound data-preservation check is accepted after the verified affected-state backup and isolated restore. Komga stays running and the permanent worker stays inactive. Historical source inventories and refused attempts remain in [evidence history](evidence-history.md).

- **Accepted native preservation:** image/publication/source, intended configuration, typed catalog records, retained downloads, backups and peer profiles close. Source-specific backfill and timestamp comparisons preserve actual raw differences. See [accepted preservation](evidence-history.md#native405-data-preservation-accepted--2026-10-20).
- **T030 cache guard accepted:** published source/image gates, restart/concurrency fixtures and the fresh configured 64 KiB allocation/refusal/accounting test pass. Exact owned-leaf cleanup, typed snapshot preservation and all unrelated source/profile closures pass. Later live contents remain outside the explicit snapshot proof; prior refusals stay retained. See [configured acceptance](evidence-history.md#configured-cache-guard-accepted--2026-10-20).
- **T026/T029 have source and execution work:** current-role capture, effective-scope production, SourceCohort and checked plan13 composition exist. The maintained active-input assembler and exact host-engine intent producer are delivered in PR #449 and independently reviewed; the delivered source successor passes 1,401 controls across 75 suites under Python 3.10, with zero skips. Its 14 outer checks and checked 27-output installation/export pass; configured connected acceptance remains open. The configured birth/session path already exists. The engine deliberately refuses unbound create/start calls; the effective-scope observer now accepts an authenticated original disposable bootstrap mapping while preserving its production mapping. Exercise those integrated producer/caller contracts against the matching images, then verify genuine connected factories, preservation and terminal consumption without fabricating approved scopes or NFS facts. Feature 024 T012/T015 shares these dependencies.
- **Fresh isolated bootstrap:** the ninth finite batch completes both genuine Mylar queue imports, reader scan/progress and restart. Its worker remains stopped and original receipts/data are retained. PR #471 is merged with passing hosted CI. Connected factories, NFS, publication, retained live-DDL and fresh ACK acceptance remain open. See [the current bootstrap record](evidence-history.md#genuine-isolated-bootstrap-completed---2026-10-21).
- **T027 physical/reader acceptance remains open:** the retained configuration/catalog and duplicate-safe protection map are planning evidence. Fresh physical coverage, optional-font protection, aliases, neutral NFS preservation and owning Parent admission remain required. Effective-scope references expire after 120 seconds. See [retained planning](evidence-history.md#new-native-configuration-and-catalog-generation--2026-10-18) and [reader observations](evidence-history.md#configured-reader-helper-startup-profile--2026-10-18).
- **T028/T033 pack recovery remains open:** all four selected histories remain retained, with no accepted import or ACK. The PR #405 worker passes 42 installed-module checks and 168 pack/import controls. Selected import, a later automatically consumed capture, restart reconciliation and fresh ACK are still required. See [installed worker proof](evidence-history.md#published-worker-installed-runtime-checks--2026-10-20).
- **T031/T032 are complete; T017–T019 retain their aggregate gates:** identity recovery and control-state adoption are accepted. Current-library, reader, restart and second-pass acceptance precede bulk resumption and final cleanup. Keep one independently verified current backup and unresolved originals. See [recovery](evidence-history.md#combined-worker-recovery-and-pack-matching-2026-10-15) and the task dependencies below.

## Remaining execution order

Use milestones rather than circular whole-task dependencies. A reviewed run may
supply evidence for several task IDs; do not repeat an accepted operation just
to create a second receipt. Each checkbox still requires all its criteria.

| Track / milestone | Tasks | Exit condition |
| --- | --- | --- |
| 1 | T028 source review; T026 source/install delivery | Reviewed contracts, matching selected-image/module proof and passing delivery gates for changed bytes |
| 2 | Shared isolated T026/T029 and feature 024 T012/T015 proof; T027 prerequisite controls | Genuine factories, archive terminal/consumption, complete preservation and actual isolated NFS/reader/restore evidence |
| 3 | T017 rollout milestone only | Current affected baseline, verified consistent backup/restore and matching generation running; T017 remains unchecked |
| 4 | T027 live proof, then finish T017 | Fresh complete physical/reader/NFS/terminal/resume proof followed by exact registration and retained-repeat acceptance |
| Pack A | T028 retained-existing-target recovery | Configured retained-parent/worker custody, authenticated finalization, fresh catalog-to-ACK and independent terminal/reader acceptance; no archive NFS prerequisite |
| Pack B | T033 ordinary selected canary, then recurring recovery | Ordinary ACK, later automatically consumed capture, restart reconciliation and retained sources; independent of T028 and archive NFS where the owning contracts permit |
| 6 | T018 current-library/bulk admission, then T019 cleanup | Applicable archive/reader/pack/restart gates and whole-library protection; only conclusively accepted copies retired |

T028's source review precedes T026; its live ACK proof is the separate Pack A
track. Pack A and Pack B follow their own stated prerequisites and do not wait
for archive milestones 1–4. T032 remains the worker-activation prerequisite.
Ordinary Mylar stays available while this implementation proceeds.
PR #482 delivered the assembler correction with passing local and hosted checks.
A fresh batch passes the causal SourceFixture, source closure, owned-container
absence, current-role/protocol observations, active assembly and intent construction.
It enters the owning producer once, then fails without an accepted terminal return.
The primary refusal is `configured-overlay-exact-approved-edits`: the packet mapped
the operation to its host path instead of the installer-owned `/_operation`. The
source correction adds an early mapping check and fixes the separate actor/finalizer
descriptor double-close. All 1,406 controls across 75 suites and 14 outer controls
pass locally; delivery, a fresh checked installation and corrected new packet remain
required under feature 023 T026. Preserve the consumed generation and all
failed histories; no automatic replay, import ACK or bulk acceptance is granted.
See [the current owning boundary](evidence-history.md#owning-producer-entry-after-assembler-delivery--2026-10-22).

## Phase 1: Setup

- [x] T001 Validate prospective requirements, researched source boundaries and complete contracts in `specs/023-verified-publication-corrections/spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/publication-corrections.md` and `quickstart.md`; complete independent design review before implementation.

## Phase 2: Payload and state foundations

- [x] T002 Implement bounded metadata-independent inventories and exact regular-member/page-order vectors in `stacks/mylar3/config/publication_guard.py` and `stacks/mylar3/config/test_publication_guard.py`; bundle the existing pinned offline archive verifier and libarchive dependency in `stacks/mylar3/Dockerfile`, proving actual ZIP/RAR/7z runtime support and held unsupported/unstable input.
- [x] T003 Implement immutable correction attestations, complete census/revision and explicit reviewed epoch initialization and prepared-marker/SQLite/final-marker missing-state binding/recovery in `stacks/mylar3/config/publication_guard.py`, `stacks/mylar3/config/native_writers.py` and `stacks/mylar3/config/workflow_store.py`; implement existing-only startup exclusion and explicit virgin creation in `stacks/mylar3/config/patch_publication_startup.py` and `stacks/mylar3/config/publication_fresh.py`; prove crash, loss, corruption, full-record coverage, contradictory owners and restart controls in `stacks/mylar3/config/test_publication_guard.py` and `stacks/mylar3/config/test_publication_startup.py`.

## Phase 3: US1 — Reviewed correction registration (P1)

**Goal**: Persist only explicitly reviewed payload/owner evidence.
**Independent test**: Registration verifies the current exact correct owner/archive, rejects stale/unreviewed inputs and safely reconciles identical replay; retagging/recompression yields the same payload identity.

- [x] T004 [US1] Add bounded prepare/commit registration, path-confined primary-key advisory checks and exact intent/census replay in `stacks/mylar3/config/publication_guard.py`, `stacks/mylar3/config/publication_api.py` and `stacks/mylar3/config/patch_publication_guard.py`; verify restricted-key denial, evidence/owner ambiguity, scope, protocol and lock order in `stacks/mylar3/config/test_publication_guard.py` and `stacks/mylar3/config/test_publication_api.py`.
- [x] T005 [US1] Install and verify the focused adapter/helper at the required manifest point in `stacks/mylar3/config/apply_patches.py`, `stacks/mylar3/config/verify_image.py` and `stacks/mylar3/config/MODULES.md`; prove repeat patching and actual image imports without source-layout assumptions.

## Phase 4: US2 — Hold conflicts before publication (P1)

**Goal**: Every native and worker mutation respects verified correction evidence.
**Independent test**: Known wrong payloads remain retained with no tags, placement, owner/status mutation, submit, false completion or cleanup; genuinely different eligible payloads continue.

- [x] T006 [US2] Guard ordinary, annual, storyarc and oneoff native postprocessing before scripts/tagging/duplicate handling and before placement/status commits in `stacks/mylar3/config/patch_publication_guard.py`, `stacks/mylar3/config/patch_publication_processing.py`, `stacks/mylar3/config/publication_native.py` and `stacks/mylar3/config/processing_guard.py`; carry explicit retained-review through `stacks/mylar3/config/pp_monitor.py` and native `process.py`; verify terminal retained-review across disabled/Legacy/Modern tagging and source-changing scripts in `stacks/mylar3/config/test_publication_native.py` and `stacks/mylar3/config/test_publication_guard.py`.
- [x] T007 [US2] Guard manual/backend tagging and converted follow-up in `stacks/mylar3/config/tagger_backend.py`, `tagger_native.py`, `tagger_service.py` and `converted_tagging.py`; add exact typed owned-job capability in `publication_transaction.py` with private internal admission through `publication_native.py`/`publication_api.py`, while ordinary `native_writers.py` admission stays held; extend their owning `test_*.py` suites to prove conflict and unavailable-state retention before publication and replay.
- [X] T008 [US2] Guard rescans and converted catalog ownership repair before row changes in `stacks/mylar3/config/file_identity.py`, `stacks/mylar3/config/converted_catalog.py` and `patch_media_writers.py` (actual manualRename/downloadLocal/moveit.movefiles/helpers.file_ops/librarysync.libraryScan branches); extend `test_file_identity.py`, `test_file_matching.py` and `test_converted_catalog.py` for annual shadows, exact rejected payloads and no row deletion/reassignment.
- [x] T009 [US2] Guard native naming, metadata supplementation and recovery/acknowledgement before source or catalog mutation in `stacks/mylar3/config/release_naming.py`, `stacks/mylar3/config/tagger_supplement.py`, `library_metadata.py`, `tagger_adapter.py` and `tagger_nfs.py` (including direct repair_nested publication, replay and reviewed derivative aliases) and their owning `test_*.py` suites; retain journal/fence/lineage contracts and block stale or conflicting proof.
- [x] T010 [US2] Implement worker advisory/version/complete-census-marker/source and fresh matched correct-owner binding and independent portable vectors in `stacks/komga/normalizer/publication_guard.py` and `stacks/komga/normalizer/test_publication_guard.py`; require native final enforcement, fresh all-row correct-owner/archive evidence under the shared writer for worker-only mutations, and avoid remote API calls under that writer. Map this into `writer_cycle.py`/`test_writer_cycle.py`: its complete conversion and maintenance cycle holds the writer, so use pre-lock immutable batch advisories or full local authority validation inside the lock. Test same-revision owner/path/content drift and missing attestations.
- [x] T011 [US2] Guard common/guided/pack import submission, existing-target confirmation, Extras placement and duplicate cleanup in `stacks/komga/normalizer/import_recovery.py`, `pack_recovery.py` and `maintenance.py`; extend their owning `test_*.py` suites to prove no submit/report/delete or prior-proof replacement on conflict.
- [x] T012 [US2] Guard conversion publication, reader/catalog notifications and naming/metadata preparation/recovery in `stacks/komga/normalizer/normalize.py` and `naming_worker.py`; extend `test_normalize.py` and `test_naming_worker.py` for old-to-new payload binding, changed registry/source and no publication on uncertainty.

## Phase 5: US3 — Retained repeat reconciliation (P2)

**Goal**: Repair exact existing repeats while preserving correct publications and legitimate wanted intent.
**Independent test**: A reviewed scoped repair verifies isolated restores, preserves the correct archive/owner/reader, retains the repeat outside the library and changes only proved false catalog claims.

- [x] T013 [US3] Document and validate the bounded registration importer and repeat-repair contract in `specs/023-verified-publication-corrections/contracts/publication-corrections.md`, `quickstart.md` and `stacks/mylar3/README.md`; private operational plans must bind actual evidence/current files and must not fabricate release provenance or overwrite the correct publication.
- [x] T014 [US3] Prepare exact private registration/reconciliation intents and verify their stale-owner/source/backup refusal controls in isolated fixtures; bind the scoped plan to `specs/023-verified-publication-corrections/contracts/publication-corrections.md` and record readiness/gaps in `specs/023-verified-publication-corrections/tasks.md` without publishing private payloads or executing live mutation.

## Phase 6: Delivery and final acceptance

- [x] T015 Update affected stack contracts together in `stacks/mylar3/docker-compose.yml`, `stack.env.example`, `stack.yaml`, `prepare-stack.sh`, `caddy_snippet.conf.example` and `README.md`, plus the matching `stacks/komga/` examples/preparation/metadata/README; document private-state backups and compatible guard protocol without adding mounts, ports or privileges. Regenerate `documents/STACK-CATALOG.md` and other generated surfaces only from affected sources.
- [x] T016 Complete independent contract/failure review, focused/native-image/worker-image checks and `make ci-local`; deliver reviewed source through `RELEASING.md` and verify matching image publication, GitHub/local/Gitea synchronization and open PR disposition. Record evidence in `specs/023-verified-publication-corrections/tasks.md`. This precedes T017 live rollout.

## Phase 7: Owning negative-retirement prerequisites

These tasks preserve earlier implementation and rollout history and retain their IDs in dependency order. T020–T025 and the retained-delivery source review in T028 precede T026; current combined runtime acceptance in T029 follows T026 and precedes the held-image rollout portion of T017. T027 executes after that rollout and before T017 reconciliation and T018–T019 acceptance/cleanup. Implementation completion requires the owning integration tests and selected-image proof described by each task. T022 requires portable owning tests and checked installation. T026 additionally requires connected owning factories, and feature 024 T012/T015 depend on that proof. T029 requires genuine installed discovery, import and archive producer/consumer execution; source parity alone does not complete these gates. Fresh configured Parent/NFS and aggregate execution remain under T027 and T017–T019, with feature 024 live acceptance under T016–T018.

- [x] T020 [US3] Define the finite aggregate retirement contract in `contracts/publication-corrections.md`, `plan.md` and `data-model.md`; bind all five native preparations, exact affected reader rows, current census/catalog and continuous existing Writer/owning stopped-reader lifetime. Install fail-closed ordinary admission for `negative-retirement-v1.pending` across native, worker and archive preparation purposes.
- [x] T021 [US3] Implement `stacks/mylar3/config/publication_negative_batch.py` with one immutable aggregate intent and exact shared-parent projections for all five sources through source nlink1, exact staged aliases nlink2 and retained target nlink1. Preserve original bytes/attributes and every unrelated namespace/claim/ancestor fact; forbid arbitrary baseline refresh.
- [x] T022 [US3] Implement the installed `publication_reader_phase.py` owning stopped-reader handoff, binding reviewed scope, main/tasks physical pairs, complete schema/typed table fingerprints, exact eleven affected rows and retained restore custody; no Docker/API call runs under Writer. Implement and test the portable owning lifecycle parent and selected-child action provider, exact command/control/profile binding, consistent full backup/isolated restore, continuous reader-stop checks, uncertain child/ACK retention and independent terminal gate before restart. Their checked installation is a prerequisite of T026 and feature 024 T012/T015.
- [x] T023 [US3] Connect all five staged reservations to exact reader SQL custody and commit in `publication_negative_batch.py` and `publication_reader_phase.py`; independently verify current paired restore and durable intent before changing only the five reviewed BOOK rows' `DELETED_DATE` and `LAST_MODIFIED_DATE` cells. Verify complete native/reader vectors after final callbacks before commit.
- [x] T024 [US3] Implement finite precommit alias rollback and postcommit exact SQL reversal followed by precise no-overwrite source restoration. Preserve foreign entries, source/custody proof and unresolved crash or lost-response evidence without automatic replay.
- [x] T025 [US3] Implement aggregate terminal verification and exact pending-marker clearance only under its existing held Writer; require all five retired originals, committed reader state, preserved proper owners, complete current census/catalog and durable matching phase receipts. Create a durable root-owned terminal successor hold before removing the aggregate marker; prove ordinary/startup refusal through crashes and lost acknowledgements until exact terminal completion.
- [ ] T028 [US3] Finish the retained-delivery route in `stacks/komga/normalizer/import_recovery.py`, `pack_recovery.py` and native `ordinary_import_history.py`: bind one exact retained capture/member and preserved current target, activate only the reviewed configured retained route, and verify its fresh catalog-to-ACK provenance plus independent terminal/reader acceptance. Preserve Wanted intent, rejected owners, original sources and all failed histories. Require the replacement, overlapping-generation, annual, crash/lost-response and no-ACK/no-cleanup controls plus matching installed images; source review precedes T026, while selected live acceptance remains separate.
- [ ] T026 [US3] Finish coherent source/install delivery in `stacks/mylar3/config/reader_recovery/genuine_active_inputs.py` and the native/worker image gates, then prove exact installed SDK types, passive hooks and connected Parent/Birth/configured factories. Preserve interruption, late source/claim/journal and SQL/reversal controls. Use the shared isolated execution below with T029 and feature 024 T012/T015; require independent review, local/hosted checks and publication of changed installed bytes. Reuse unchanged image proofs only for matching original inputs; component tests alone do not complete this task.
- [ ] T029 [US3] Run `stacks/mylar3/config/reader_recovery/genuine_plan13_producer.py` through genuine configured factories with fresh original roles/scope/cohort/assembly/intents; prove actual NFS/reader custody, causal archive forward/rollback terminal production and intended native/worker consumption. Complete installed discovery, ordinary import success/lost-response and import-to-rename metadata continuity in `stacks/mylar3/config/verify_image.py` and owning worker gates. Retain source/namespace/journal vectors and independent terminal/ACK evidence; unknown outcomes prohibit replay. Resolve namespace gaps within the existing mount/privilege contract and pass delivery gates before T017 selects changed images.
- [ ] T027 [US3] Use `stacks/mylar3/config/reader_recovery/CONTRACT-nfs-factual.md` and the owning lifecycle/proof tools for actual NFS hardlink/fsync, exact cleanup and reader preservation. Share isolated controls with T026/T029, then after the rollout milestone of T017 capture fresh complete live scope, optional fonts/aliases/protected roots and consistent backup/isolated restore. Require actual stopped-reader, forward/rollback, independent terminal and guarded-resume proof before T017 reconciliation or T018/T019 release; prepared/local evidence is insufficient.

## Phase 8: Independent DDL cache capacity guard

- [x] T030 [US3] Implement FR-016 cache growth prevention in the owning Mylar intake/reservation and retained-capture paths, with configurable cache byte budget and processing headroom shared by participating worker `.mylar-pack-*` stages, existing-only policy/lock consumption, exact finalized output sizing, no-follow bounded accounting, unresolved-delivery deduplication, restart/concurrent admission and capacity-refusal tests. Update the owning stack contracts and image gate; deliver with passing local/hosted checks, then verify the configured live guard without deleting retained originals or manufacturing ACKs. This independent follow-up can proceed alongside T017/T027 recovery; it does not replace their backup or import acceptance.

## Phase 9: US3 — Live acceptance and scoped cleanup

- [x] T031 [US3] Correct the tagger identity reader's finite history traversal so valid terminal history beyond 4,096 entries remains admissible, using strict owning parsers for both legacy version 1 and native version 2 journals without publication-job callbacks. Preserve receipt parsing, ownership, original-file checks, active-lock exclusion and the unresolved-staging hold; prove real large-history acceptance plus unsupported-version, malformed, oversized and retained-state refusal. Integrate the exact source pins and image gates, deliver with passing CI, and verify the selected native image before post-reboot identity recovery. This prerequisite of T017 does not authorize deleting history or replaying retained staging.
- [x] T032 [US3] Deliver explicit worker control-state device adoption without rewriting `normalizer-state-v1.identity`: reviewed affected-control backup/isolated restore, original state/jobs inode and namespace custody, current accepted native edge and prospective Btrfs filesystem/subvolume binding, read-only default refusal, in-flight/unknown/foreign refusal and interrupted-commit hold. Classify bounded controls by owning role; preserve passive reports, uncertain legacy submitted dedup history and unsent notifications unchanged without granting replay or ACK, with exact current native terminal/absence proof for retained guidance review. Preserve only complete exact legacy cross-role payload alias sets as metadata; keep controls/proofs single-link and require actual publication_roots configuration and genuine scoped acceptance. Verify the installed matching worker image and exact reviewed binding before experimental worker activation. Preserve all job receipts and retained payloads; this does not require copying unrelated completed-job payloads or complete T017/T030.
- [ ] T017 [US3] After T026/T029 isolated readiness, follow `stacks/mylar3/README.md` and `stacks/komga/README.md` to record the affected baseline, verify scoped consistent backup/isolated restore and deploy matching native first when required. Release the external deployment guard before ordinary Mylar startup; preserve durable operation holds and experimental bulk inactivity. After T027 live terminal/reader proof, use the exact correction-registration and retained-repeat APIs to reconcile only accepted current owner/census/archive/database evidence; record results here.
- [ ] T033 [US3] After matching-image proof, T032, affected-state backup/restore and an eligible ordinary selected-pack canary, enable only the explicit `stacks/komga/docker-compose.packs.yml` recurring mode implemented by `normalizer/pack_only.py`. Prove a canary, a later capture consumed without manual invocation, restart/lost-response reconciliation, fresh catalog-to-ACK and source preservation. Preserve default full mode and busy/pending/malformed/capacity refusal; no general maintenance, naming, conversion, workflow/catalog fallback, reader-scan or bulk permission follows.

- [ ] T018 [US3] Execute the conflict/different-payload vectors in `specs/023-verified-publication-corrections/quickstart.md`, then verify complete current-library bytes, owners, readers, catalog, restart/retention and second-pass behavior. Resume experimental bulk only after protected current-library acceptance and applicable pack/reader gates; preserve durable holds. Record shared feature 024 T018 proof and feature 022 T024 post-bulk idempotence separately in the owning task files.
- [ ] T019 [US3] After accepted terminal/current-library/pack/restart outcomes, retire only conclusively completed operation-owned temporary preservation/restore copies through the owning status/cleanup routes documented in `stacks/komga/README.md`. Keep one independently verified current backup, unresolved originals, correction/quarantine evidence and uncertain histories. Verify exact cleanup ownership, absence and surviving data, then update feature 022 acceptance; age, a Completed label or source-test success is insufficient.

## Dependencies and execution

T001 → T002–T003 → T004–T005 → T006–T012 → T013–T015 → T016 reviewed delivery → T020–T025 plus T028 reviewed recovery → T026 integration → T029 connected runtime acceptance → T017 held rollout → T027 fresh restore/NFS and aggregate terminal proof → finish T017 reconciliation → T018 → T019.

Ordinary post-reboot recovery follows T031 → the scoped native recovery portion of T017, independently of experimental Parent, NFS and bulk acceptance. Its consistent backup and selected-image checks remain mandatory. T033 restricted ongoing ordinary pack recovery follows the selected-path delivery and T032 control-state acceptance, with its own matching-image, backup and live ACK proof. T032 gates subsequent experimental worker activation separately; it does not hold ordinary native availability.

T020, T021 and T023–T025 are complete as implementation milestones: independent review confirms admission exclusion, five-owner staging, exact SQL transitions, reversal, terminal succession and crash/lost-response refusal. Evidence includes the merged PR #293 full-image gates, installed native source/type parity and the actual Btrfs 191 standalone/132 authenticated controls, with no skips. The earlier blanket note incorrectly kept these implementation tasks open until live acceptance. Their completion does not authorize execution: configured stopped-reader/parent admission, matching worker acceptance, consistent restore and live terminal proof remain under the unchecked T026–T029 and T017–T019. T028 still needs authenticated operational launch.

T017 retains the verified 12-scope outer backup and isolated restore with all 72 database checks, bootstrap authority and 13 correction-family registrations. An earlier ordinary repair verified its native-only backup, rollout, queue health and catalog preservation; those historical results do not establish current post-reboot recovery. Failed backup attempts remain in evidence history. T017–T019 remain open for configured archive/ownership recovery, aggregate terminal proof and experimental/bulk acceptance. T018 supplies the current-library acceptance shared with feature 024 T018; feature 022 T024 separately proves post-bulk idempotence and final data acceptance.

### Next action and completion evidence for each open task

| Task | Next bounded action and inputs | Evidence required to mark complete |
| --- | --- | --- |
| T026 | PR #482 is delivered. Deliver the reviewed common-root descriptor fix and early operation-child check with their coordinated source pins. Create a new checked installation and fresh original bindings; map the new operation to the installer-owned `/_operation`, keeping the other five mount rows unchanged; preserve the consumed G attempt and unchanged SDK proofs only for their exact inputs. | Current source manifests/review/delivery; exact selected-image byte/type/import proof; genuine connected factories and final source/namespace closure. Historical source counts and the successful projection remain partial evidence. |
| T029 | Follow `genuine_current_roles.run` → `genuine_active_inputs.assemble` → `comic_nfs_host_engine.build_intents` → `genuine_plan13_producer.Producer.execute(activate=True)` → `LifecycleParent.execute_archive`. Bind the continuation before fresh observations expire; never retimestamp them. | Original execute ACK, original source and physical/SQL vectors, causal archive transition, independent terminal and native/worker factual consumption; complete installed import/lost-response/naming-continuity checks. Unknown outcomes remain held. |
| T017 | Coordinate writers and follow the owning rollout route. For registration/reconciliation use `scripts/prepare-publication-corrections.py`, native registration preparation/acceptance, a fresh retained-repeat plan, `commitRetainedRepeat` and passive `retainedRepeatStatus`. | Verified backup/restore, exact image/config/data baseline, accepted registration/token/status, wrong repeat outside the scanned library, correct owners/bytes/readers and database integrity unchanged. Complete only after T027 and the required retained paths succeed. |
| T027 | Use the maintained NFS factual/reader-proof contracts with original operational geometry and mount/source refs. Retain custody through canary cleanup, Writer release, reader stop, backup/restore and independent terminal verification. | Actual readiness and owned cleanup; checked factual owner; stopped-reader and database-restore controls; terminal/reader resume proof and complete final physical coverage. Disposable Btrfs helper tests do not prove actual NFS or lease behavior. |
| T028 | Bind reviewed configured source/pins for `publication_retained_api.py`, `publication_retained_finalize.py`, `reader_recovery/comic_retained_pack_parent.py` and worker `retained_pack_handoff.py`; portable defaults stay disabled. Verify fixed image anchors, UID1000 original refs, the same-live worker pipes, measured two-copy backup capacity and actual restore before one retained member action. Use authenticated finalize/status and the owning independent terminal/restart contracts. | Exact current capture/member/source/target/owner and catalog event, fresh ACK, terminal SQL/reader preservation and compatible restart. The parent prefix returns no completed custody/resume grant. Generic `--pack-capture` refuses `retained-accepted` members and cannot substitute for this route. Preserve all failed histories and uncertain replies; never manufacture historical ACK or retire a source before fresh acceptance. |
| T033 | First use documented `--pack-capture <sha256> --pack-ddl <id>` for one eligible ordinary capture with configured mappings, current Writer/publication/reader checks and verified affected-state backup. Then use `docker-compose.packs.yml` last with `--packs-only`; `--packs-only --once` proves only a bounded canary. Selected flags and recurring mode are mutually exclusive. | Ordinary selected ACK plus a later new capture consumed by the ongoing mode without another invocation, restart/lost-response reconciliation, fresh health and retained originals. Existing-target retained recovery stays under T028. Neither T028 completion nor archive NFS proof is a prerequisite of this ordinary path; general/bulk permission remains separate. |
| T018 | Apply the quickstart conflict/different-payload vectors and complete the current correction-family census, covering metadata on/off/Legacy and ordinary/annual/storyarc/oneoff paths where applicable. | No wrong publication, source deletion or false completion; correct owner/reader/database baseline, restart retention and complete current-library/second-pass evidence before explicit bulk resume. Later post-bulk acceptance belongs to feature 022 T024. |
| T019 | Derive each cleanup candidate from its accepted exact operation receipt and original ownership; inspect status before calling its typed cleanup route. | Per-copy accepted disposition, exact owned absence, surviving current verified backup and preserved unresolved originals/history. Cleanup carries no additional import, reader or bulk rights. |

## Parallel opportunities

Independent design/contract and failure-path reviews can inspect a frozen candidate concurrently. Native and worker isolated fixture checks can run separately. Shared source integration, Git, generators, registry admission and all live media/catalog writers stay under one coordinator; no unfinished implementation is marked `[P]`.

## Implementation strategy

Build the immutable reviewed-registration MVP first, then prove every publication boundary before claiming prevention. Keep existing-repeat repair separate from detection. Continue source and isolated checks while keeping the default worker held; record operational acceptance gaps explicitly.

## Evidence

The build-warning follow-up preserves parsing and transaction behavior while
fixing deprecated calls and resource leaks. Its accepted native capture and
matching installer are recorded below; the source correction alone does not
complete connected acceptance. See [the correction record](evidence-history.md#build-warning-corrections--2026-10-21).

T001–T016 authority foundations and guarded publication paths are accepted.
T022's portable lifecycle/checked installation, T031 identity recovery, T032
control-state adoption and T030 configured cache guard are complete. Published
ordinary import/rename/metadata and worker component proofs remain in
[evidence history](evidence-history.md); they do not complete current connected,
retained-download or bulk acceptance.

The accepted native405 preservation baseline and published449 component proofs
remain valid for their recorded versions. The PR #462 native180/startup capture
and matching 27-output supplier pass. Current source checks are summarized below;
original installation outputs and failed generations remain retained.

## Convergence assessment and evidence

PR #463 scheduling and PR #464 cacheable stages are merged. The tagging stage's
117 tests pass without skips, and an unrelated reader edit reuses that layer.
See [cacheable stages](evidence-history.md#cacheable-image-verification-stages--2026-10-21).
PR #471 delivers the current 1,302-control/73-suite source proof after passing
hosted CI. The ninth isolated bootstrap also completes genuine processing,
reader and restart checks; [the current bootstrap record](evidence-history.md#genuine-isolated-bootstrap-completed---2026-10-21) preserves
the distinction from still-open connected and live acceptance.

T017–T019 retain their aggregate rollout/library/final gates. T026/T029 require
genuine connected factories and archive terminal consumption, T027 physical and
reader acceptance, and T028/T033 selected import, fresh ACK and later automatic
capture consumption. All selected histories remain retained; the permanent
worker remains inactive. Component source tests do not complete these tasks.

Clark PR #460 and the original generation preparation remain recorded in
[evidence history](evidence-history.md#next-generation-preparation-and-clark-integration--2026-10-21).
Host-only control changes do not refresh the original 27 installation outputs
or require another image pull when the installed SDK remains unchanged. Fresh
source and connected runtime acceptance still precede their owning operations.

The old PR #341 worktree documentation has been reconciled against current
history. Its exact patch and verified Git bundle are preserved privately, and
the old worktree is removed without force.
See [recovered storage notes](evidence-history.md#recovered-storage-notes-and-old-worktree-cleanup--2026-10-21).
