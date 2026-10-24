# Tasks: Verified comic release naming

**Input**: Design artifacts in `specs/022-comic-release-naming/`.
**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/naming.md` and `quickstart.md`.
**Organization**: Setup and foundations precede three independently testable user stories and final acceptance. Completed evidence is retained below; unchecked tasks require their full acceptance proof.
**Format**: Sequential `TNNN` IDs; `[US1]`–`[US3]` label story tasks. `[P]` is reserved for independent implementation in different files, with no incomplete dependencies.

**Current delivery requirement (2026-10-10)**: Hosted CI must pass before any further merge. The user has revoked the outage waiver; historical waivers in the linked evidence history do not authorize new exceptions. Fix failing checks while preserving their acceptance assertions.

## Current remaining work

**Updated 2026-10-24.** 21 of 24 tasks are complete. T019/T023 require configured
recovery and current-library acceptance before the combined naming/metadata
passes; T024 proves final idempotence, preservation and cleanup afterward.
Preserve dotted fields and the hyphen before the verified release group.

The immediate shared recovery work is owned by [feature 024's current
work](../024-verified-archive-repair/tasks.md#current-remaining-work). Reuse its
accepted evidence where applicable; this feature requires no additional archive
fixture or repeated source-delivery gate. Installed naming/metadata component
proof and the accepted ordinary native baseline retain their recorded scope.
The permanent worker and combined bulk pass stay inactive. The separate
reading-progress audit remains deferred.

The older backup index supplies no exact candidate for 19 historical missing DDL
originals. Keep that gap and the four selected-pack histories separate from
current-library acceptance; no selected import or ACK is accepted. Historical
proof and refusals remain in [evidence history](evidence-history.md) and the
[shared history](../023-verified-publication-corrections/evidence-history.md).

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
- [ ] T019 [US3] After feature 023 T026/T029 matching-cohort proof and T017/T027 rollout/physical-reader proof plus T018 current-library admission, finish the remaining eligible combined rename/metadata pass through `Naming.plan/apply` and `Combined.advance` in `stacks/komga/normalizer/naming_worker.py` and `combined_handoff.py`, using native `combinedPublication` and `tagger_supplement.apply_preserved`. Bind a fresh reviewed manifest to current sources, catalog, reader hashes and approved additions; apply one canary then bounded serial batches. Done requires unchanged-hash reader restoration before metadata, exact final payload/ownership/pages/readiness, truthful pack bindings and conclusive per-entry cleanup, with every excluded or held entry recorded and exact-path credit deferrals preserved.
- [x] T020 [US3] Deliver and verify the corrupt-ZIP fallback fix in `stacks/komga/normalizer/maintenance.py` and `stacks/komga/normalizer/test_maintenance.py`; prove bounded missing-end-record detection, retain dependency/unknown failures, and verify scoped preservation/native failure recovery under a completed bulk checkpoint. Persist guarded retry intent before volatile search submission in `stacks/mylar3/config/failed_downloads.py` with restart, queue-failure and ownership-drift regressions in `stacks/mylar3/config/test_failed_downloads.py` and actual native committed-cursor tests in `stacks/mylar3/config/test_database_transactions.py`; deliver the native image and reconcile the existing exact failed owner without replaying failure processing or search.
- [x] T021 [US3] Deliver and verify ComicInfo-preserving import confirmation in `stacks/komga/normalizer/maintenance.py`, `stacks/komga/normalizer/guided_match.py`, `stacks/komga/normalizer/test_maintenance.py` and `stacks/komga/normalizer/test_guided_match.py`; require exact ordered pages/all non-root-metadata extras, matching publication identity and both ZIP root metadata files, a verified retained original, stable hashes and truthful cleanup receipts, covering interruption/storage/link/mutation failures before live reconciliation.
- [x] T022 [US3] Preserve confirmed pack evidence through native naming and metadata publication in `stacks/mylar3/config/pack_bindings.py`, `stacks/mylar3/config/tagger_pack.py`, `stacks/mylar3/config/release_naming.py`, `stacks/mylar3/config/tagger_supplement.py`, `stacks/mylar3/config/tagger_native.py`, `stacks/mylar3/config/tagger_adapter.py`, `stacks/mylar3/config/workflow_store.py` and `stacks/mylar3/config/patch_pack_intake.py`; capture durable exact-owner/path/hash transitions before mutation, atomically rebind all matching confirmed members before fence clearance, preserve sidecars/history and reject stale or foreign evidence. Add rename, metadata, interruption, multi-pack, replay and ownership/content regressions in `stacks/mylar3/config/test_pack_bindings.py`, `stacks/mylar3/config/test_release_naming.py` and `stacks/mylar3/config/test_pack_records.py`; complete independent review, image/repository gates and verified rollout before resuming bulk.
- [ ] T023 [US3] Verify the delivered numeric-title, print-run/four-digit-issue/publication-year and redundant verified `#issue` corrections in `stacks/mylar3/config/release_naming.py`, `patch_release_naming.py` and `stacks/komga/normalizer/release_naming.py` on the selected generation, retaining their parser/renderer regressions. Reconcile any remaining proven rejected entries only through `Naming.recovery_entry` and distinct version-2 `retry_of` children with both verified copies, original ownership and reader proof; retain rejected predecessors and reconcile uncertain children without replay. After the T019 combined pass, refresh the supplement preview for canonical/later-intake archives excluded from its frozen candidates, apply only independently proven metadata additions, and rebind repaired-file credit deferrals only through exact old-to-new receipts before supplementation. Done requires archive/native/reader acceptance for every eligible remaining entry and an explicit unchanged hold for every unresolved credit, edition, identity or source. Preserve the deferred additional reading-progress audit and existing safeguards.

## Phase 6: Final acceptance and cleanup

- [ ] T024 After T019/T023 and shared feature 023 T018 acceptance, run a fresh current-library naming/supplement preview and verify second-pass idempotence, exact archive/attributes/catalog/reader preservation and service health. Retire only conclusively completed operation-owned temporary preservation/restore copies through the owning typed cleanup/status route; uncertain results remain status-only and retained. Keep one independently verified current backup, immutable journals/audit receipts and unresolved originals. Record the final coverage, exclusions, cleanup and service/data evidence in this file and `specs/022-comic-release-naming/quickstart.md` before marking complete.

## Dependencies and execution

Setup T001–T003 → foundations T004–T007 → US1 T008–T011 → US2 T012–T013 → US3 T014–T023 → final acceptance T024. T015 review/delivery and T016 verified rollout precede live bulk admission. T017–T018 identity corrections are verified. T019 began with a verified combined canary and remains open until the entire eligible pass finishes. The worker portions of live-discovered T020–T021 passed before resumed T019/T023 admission at the 559-publication checkpoint. T020–T021 are accepted; the additional native retry-durability rollout passed at the completed 772-publication checkpoint before further combined admission. T022 passed reviewed delivery, verified native rollout and the Grimm pack canary at 931 completed publications before further T019/T023 admission. Resumed T019/T023 and T024 also require spec 023 T009–T016 enforcement/image/delivery gates and T017/T018 coordinated current-library acceptance. T024 depends on T019–T023 acceptance; interrupted or uncertain copies remain retained.

### Remaining task execution notes

These tasks finish configured acceptance; their maintained naming, combined-publication,
predecessor recovery and pack-binding implementations already exist. Historical
2,867-file acceptance and seven completed predecessor-bound repairs remain evidence,
not work to replay. A new source defect gets its own focused repair only if the
current-source checks demonstrate one.
The current shared blocker is feature 023’s genuine connected recovery profile
check before reader stop; feature 023’s evidence history owns its diagnosis.
Naming implementation remains delivered, and these three tasks await their
explicit configured/current-library prerequisites rather than another naming
rewrite.

| Task | Inputs and next bounded action | Observable completion evidence |
| --- | --- | --- |
| T019 | Confirm the prerequisite feature 023 receipt set and fresh restore-verified affected-state backup. Use the current native naming/combined-preview capabilities, native catalog, complete reader enumeration and privately reviewed source/hash/policy/additions preview to generate `--naming-plan` with `--naming-reviewed-preview`. Review differences from the retained manifest, including later arrivals, then use `--naming-apply --naming-limit 1` for the first eligible canary. Reconcile its receipt before admitting another bounded batch. | Every eligible current manifest entry has a terminal native rename/metadata lineage and worker receipt; rename preserves archive bytes and attributes, reader restoration at that hash precedes metadata, and final member/page/root-metadata, owner/status/location and reader readiness/progress match the approved change. Confirmed pack members follow only exact owner/path/hash transitions; sidecars and unrelated members/records stay unchanged. Completed per-entry retirement has conclusive native cleanup and fresh final reader/publication proof; uncertain entries remain held. |
| T023 | Start with a status/coverage inventory of the seven historically completed child repairs and remaining review/credit/Extras holds; do not submit them again. For an actually outstanding proven rejection, call the explicit `recovery_entry` with its immutable predecessor receipt and valid detached original/restore pair, then use the ordinary fenced native/reader path. After T019, refresh the default-read-only `tagger_supplement.py` preview over canonical and later-intake files; independently review additions and credit provenance before a scoped apply. | Selected-image parser/renderer tests cover the delivered title/issue/year rules. Each newly needed recovery has a distinct child token, exact predecessor digest and final native/reader acceptance while its parent remains unchanged. Supplement coverage includes files omitted from the frozen combined manifest; each eligible addition has retained before/after identity and payload/member preservation. Credit deferrals follow verified old-to-new receipt lineage, never inferred names/hashes; unresolved credits and ambiguous or changed identity remain explicitly held. |
| T024 | Re-enumerate the whole current library after T019/T023 acceptance, including later arrivals and corrected review locations. Generate a fresh naming/combined/supplement preview, compare it with current receipts and classify every proposal/hold. Use `Combined.cleanup`/status only for a conclusive exact operation, then verify health and retained data after the final bounded cleanup. | No eligible duplicate naming or metadata work remains. Accepted files, native ownership/journals and reader book/page identity/readiness/progress agree with the final baseline; held files are inventoried without mutation. Native terminal retirement proof and matching worker `cleanup-complete` receipts identify every removed per-file pair. The final inventory confirms required current backup and unresolved originals remain, and documents any service/worker admission separately under feature 023. |

The maintained entry points and options are documented in
`stacks/komga/README.md` (Verified release naming) and
`stacks/mylar3/README.md` (Reader metadata supplementation / combined publication).
A configured naming proposal API may reconcile journals under Writer; report that
separately from read-only host/archive/reader checks. Do not treat preview output
as ownership, credit approval or permission to replay a rejected operation.

Task IDs now follow execution order. Earlier appended-task references were updated consistently in the retained evidence: former T019→T017, T021→T018, T020→T019, T022→T020, T023→T021, T017→T022 and T018→T023. This ordering correction preserves completed history and does not claim these later corrections were planned before discovery.

## Parallel opportunities

- US1: isolated renderer fixtures and native parser fixtures can run independently after T008–T010; they have separate temporary data.
- US2: native journal and worker acknowledgement/fence tests can run independently after their implementation is frozen.
- US3: read-only contract review and isolated failure-path review can run independently against one fixed candidate after T014 or a discovered repair. Live archive, catalog, reader and Git writes stay serialized under the designated coordinator.

No implementation task is marked `[P]`: the remaining tasks depend on the same coordinated media state or delivery gates. The user authorized parallel implementation through bounded units in separate worktrees. Each unit has one source owner and frozen dependency handoffs; shared manifests, contracts, generators, Git and live state retain one integration owner. Independent final review is required for substantive PRs.

## Implementation strategy

Deliver US1 as the opt-in naming MVP, verify US2 recovery gates, then roll out US3 with backups, one canary and bounded serial batches. Pause at completed checkpoints for newly discovered repairs, reconcile accepted operations before new admission, and finish with idempotence and cleanup proof. Mark completion only after the stated acceptance evidence succeeds.

## Current evidence

Naming foundations and earlier live canaries are accepted under T001–T018 and
T020–T022. The combined bulk pass, supplement reconciliation and final
idempotence remain open under T019/T023/T024. Published ordinary-pipeline tests
cover import, dotted release rename and preserved metadata, including existing
`ComicInfo.xml` position. They do not complete the configured combined pass.
See [the shared pipeline proof](../023-verified-publication-corrections/evidence-history.md#published-ordinary-pipeline-proof-and-pending-data-acceptance--2026-10-18).

Earlier image, bootstrap and lifecycle deliveries retain their recorded scope
in [shared evidence history](../023-verified-publication-corrections/evidence-history.md).
They need no separate naming fixture or repeated source-delivery gate. The
current connected pair is owned by [feature 024](../024-verified-archive-repair/tasks.md#current-remaining-work).
T019/T023 still require the remaining configured/library pass and T024 its final
idempotence and cleanup proof. Detailed failed attempts remain historical;
reading-progress work stays deferred and original recovery evidence retained.
