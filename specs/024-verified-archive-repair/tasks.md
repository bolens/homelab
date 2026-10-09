# Tasks: Verified archive repair

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

- [ ] T011 [US3] Implement the dedicated same-payload native repair capability in `publication_archive_owned.py`, `publication_native.py` and `publication_api.py`; prove fresh complete owner/census/catalog/source/stage/custody checks without widening nested lineage, ordinary `require` or generic import.
- [ ] T012 [US3] Integrate exact reader continuity, finite phase/CAS and filesystem preservation/rollback in the owning native and normalizer processing boundaries; test complete affected book/page reference preservation and zero unrelated row/member changes.
- [ ] T013 [US3] Integrate durable preparation/dispatch/acceptance/rollback history and native/worker recovery consumption in owning workflow/import modules; lost acknowledgements retain evidence, imports/cleanup wait for actual terminal acceptance, and no remote call runs under Writer.

## Phase 6: Delivery

- [ ] T014 Update Mylar/Komga README and inspect their Compose, environment, metadata, preparation and ingress contracts together; diagnostics reuse existing settings/mounts/ports/privileges and introduce no new dependency. Regenerate affected catalog sources only through owning generators.
- [ ] T015 Complete independent integrated failure review, actual selected-native/worker source-image tests, focused checks, `make validate` and `make ci-local`; deliver reviewed source through `RELEASING.md` and record source/image proof in this file. GitHub CI waiting is waived by the user; local required checks remain required.

## Phase 7: Scoped live acceptance

- [ ] T016 Coordinate writers, capture fresh affected-state/reader/native baselines, measure and create consistent backup plus independently verified restore, then deploy compatible matching images following owning READMEs; record exact actual image/process and private evidence digests in this file.
- [ ] T017 [US3] Execute the supported retained-original repair through its dedicated owning route, verify actual archive/owner/catalog/reader state and guarded repeat handling, and reconcile DDL only through actual ordinary import acknowledgement; update feature 022/023 acceptance evidence without claiming general writer release prematurely.
- [ ] T018 [US3] Verify restart, rollback/lost-response refusal and complete current-library acceptance; finish feature 022/023 release gates and prune only conclusively superseded operation-owned copies while retaining one independently verified current backup and unresolved originals.

## Dependencies and execution

T001 → T002–T003 → US1 T004–T007 → US2 T008–T010 → US3 T011–T013 → T014–T015 reviewed source/image delivery → T016 verified live rollout → T017 scoped repair/import → T018 final acceptance/retention. US1 is independently deliverable; it does not complete US2/US3 or release features 022/023. IDs follow execution order. No production task is complete from earlier private experiments.

## Parallel opportunities

Bounded source proposals and independent preservation/failure reviews may run concurrently. Root alone owns tracked integration, generators, Git, image execution and live state. Shared module/API/census/reader contracts are sequential dependencies, so no unfinished task is labeled parallel.

## Implementation strategy

Deliver truthful diagnostics first while implementing the separate owning capability. Preserve all existing ordinary and nested boundaries. Continue the already authorized feature 023 negative-publication recovery in a separate source scope; both flows share final library, reader and writer-release acceptance.

## Evidence

- Preliminary evidence (2026-10-08): private package controls and selected-runtime tests pass, and an isolated private repaired copy preserves all 30 members, 28 ordered pages, root metadata and compressed content from the scoped original. The original full signature/hash is unchanged and the test container is retained stopped. No production source installation, owning adoption or live import is inferred. Source-only diagnostic integration is under independent review.

- Design review (2026-10-08): independent review accepted the prospective spec, plan, research, model, contract and ordered tasks. All 11 affected Markdown files pass lint and the working diff passes whitespace validation. This completes the design review. Owning repair preparation/adoption and live acceptance remain open.

- US1 source progress (2026-10-08): native and worker diagnostics are integrated with exact generated module/test parity, installed-function capability checks and fixed retained-history/report messages. Each new host set passes 21 preservation, 26 stable-source and 9 owning-path controls. Staged local CI passes, including repository validation and secret scanning. The matching worker image passes all 500 controls without skips. The native baseline image passes 1,317 controls across 80 suites without skips. Its final supplement correction passes all 32 maintenance and 10 pack-binding controls in an isolated non-root image layer built from that exact baseline. Supplement authority ignores read access time while binding SQLite reads to the original open descriptor and preserving full file/parent identity and mutation checks. Independent review clears the integrated diagnostic-only source. This completes T002–T007. No live image rollout or repair adoption ran.

- Owned preparation review hold (2026-10-08): the source-only prototype passes 40 host controls, but independent review reproduces a transient directory replacement that can return a foreign read descriptor while the original pathname and parent identities are restored. That prototype is not integrated or installed. The correction must bind every hash, byte read, copy and readback to its expected open descriptor and enforce xattr bounds before bulk reads. T008–T010 remain open.

- Owned preparation correction (2026-10-08): the corrected source-only prototype pins directory/file descriptors for reads and private copies, enforces xattr bounds before reads and passes 47 host controls without skips. Independent review reproduces the original alias race and verifies the corrected original custody. Authenticated preparation/status routing is a separate source-only proposal. Neither proposal is integrated or installed, so T008–T010 remain open.

- US2 source integration (2026-10-08): the independently reviewed preparation/status source is installed with exact current Controller/Writer and catalog-derived source, bound descriptor reads/private creation, exclusive custody and passive status. Owning routes and negative-retirement purpose guards have 102 native and 60 worker host controls. Actual installed-SDK/image verification remains pending, so T008–T010 remain unchecked and no adoption or live acceptance is claimed.

- Final-boundary correction (2026-10-08): independent review reproduces a late inactive catalog alias after ordinary-purpose checks. The corrected source moves all semantic callbacks before the complete direct claim/absence closure. Both regressions now retain review, and the 100-control source gate passes. The corrected native runtime and full worker image gates remain pending.

- Corrected source gate (2026-10-08): independent review repeats both late catalog-alias and late negative-marker faults and verifies terminal refusal after the complete final direct closure. All 102 native host controls pass without skips, staged local CI passes, and the full worker image passes 504 controls without skips. The corrected native installed-image build is waiting for OS authentication. T008–T010 remain open until that gate passes. No live repair or writer release ran.

- US2 installed-image acceptance (2026-10-08): the corrected native image passes 298 selected controls across nine suites without skips, including all 102 preparation/routes/purpose controls and the genuine installed Controller/Writer factory check. The final worker image passes all 504 controls without skips; its read-only non-root smoke verifies 28 runtime module hashes, zero effective capabilities and diagnostic-only repair classification. Exact native and worker image identities are retained privately. This completes T008–T010 for preparation/status only. Adoption, aggregate reader/native recovery, live rollout and current-library acceptance remain unfinished. All 161 controls across the five suites changed by current main also pass without skips in the exact candidate image. Local merged CI and final documentation hooks pass.

- Repair admission progress (2026-10-08): archive preparation/status now refuses either negative-retirement hold through its final direct checks. The shared native and worker Writer guards cover the terminal successor, closing the interruption window before ordinary processing can resume. All 130 affected host controls pass without skips. Dedicated repair adoption, exact reader preservation, durable dispatch and rollback remain under implementation in T011–T013. These checks do not establish installed-image or live adoption acceptance.

- Recovery implementation progress (2026-10-09): the source adds both archive-repair pending/terminal markers to native and worker Writer admission and the final direct preparation/status checks. All 108 affected host controls pass without skips, including malformed markers, recovery-flag refusal and markers introduced by the last callback. Independent review repeats both marker names after each last callback and confirms refusal. The selected Mylar Python 3.10 runtime passes all 99 native controls without skips in an isolated container using public source and disposable fixtures; this is runtime compatibility proof, not installation or live recovery acceptance. The live Mylar source check confirms its explicit DATA directory before configured-root binding; no service or library state changed. Reader admission, WAL commit/rollback and parent/provider integration remain under review. No live recovery, DDL import or broad library acceptance is inferred.
