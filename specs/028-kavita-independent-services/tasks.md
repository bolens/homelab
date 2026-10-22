# Tasks: Independent Kavita provider services

## Setup and foundation

- [x] T001 Record scope, pinned source, source ownership and acceptance in spec.md, plan.md and contracts/gateway.md.
- [x] T002 Implement authenticated private gateway, bounded fixed-origin transport, cache and confirmed receipt store in stacks/kavita/providers/ with failure tests.

## User story 1: Metadata and discovery

- [x] T003 [P] [US1] Implement Hardcover and MangaBaka metadata/covers/recommendations/reviews adapters and fixture tests in providers/metadata.py and providers/test_metadata.py.
- [ ] T004 [US1] Verify genuine Hardcover and MangaBaka read payloads and field mapping, preserving account privacy.
- [x] T005 [US1] Implement the permitted ComicBookRoundup publisher-index/exact-URL connector and critic/user review fixtures in `providers/cbr.py` and its tests. Retain incomplete coverage explicitly.

## User story 2: Personal reading synchronization

- [x] T006 [P] [US2] Implement direct-provider sync adapters and failure/retry tests in providers/sync.py and providers/test_sync.py, with missing credentials explicit.
- [x] T007 [US2] Implement provider OAuth onboarding/refresh with expiring single-use state, exact callback binding and secret-free diagnostics where native PAT input is insufficient.
- [ ] T008 [US2] Verify each provider/action against exact documented schemas and intended account. Other credentials remain placeholders until supplied.

## User story 3: Application integration and operation

- [x] T009 [P] [US3] Implement pinned custom fork patch/build in independent/ with independent capabilities distinct from paid-subscription status and official-mode regression checks.
- [x] T010 [US3] Add opt-in Compose override, env placeholders, private state, preparation and ingress guidance and metadata/README changes.
- [x] T011 [US3] Run focused tests, pinned patch validation, isolated Compose/preparation and make validate; record skips.
- [x] T012 [US3] Build and smoke-test gateway/fork images against disposable state, preserving LinuxServer config/UID behavior.
- [x] T013 [US3] Capture and verify stopped application-state backup/isolated restore before live recreation; compare library/progress/user baseline after deployment and verify rollback if needed.

## Dependencies and parallel work

T001 defines the adapter contract. T002/T003/T006/T009 can proceed in parallel against it with separate file ownership. T010 follows gateway/fork configuration decisions. T011 precedes T012; T012 precedes T013. The user authorized deployment with credential placeholders, so T013 can validate local operation while credential-dependent acceptance remains open. Full parity remains incomplete until T004/T008/T026 and all requested provider behaviors are proven.

T012 evidence: both images build, native app startup and final rebuilt-gateway smoke pass. The disposable app was removed. Later image changes require targeted rebuild/smoke evidence.

## Library count repair

- [x] T014 Diagnose catalog/export/index counts without exposing book metadata; implement conservative read-only import planner and export publication safeguards with fixtures.
- [x] T015 Capture stopped Calibre, export, Kavita and Calibre-Web state; verify byte/ownership restores, SQLite integrity and NFS attribute roundtrips.
- [x] T016 Rehearse supported imports against an isolated full library copy. The first rehearsal detected recycle-bin cleanup. A second rehearsal preserved the recycle bin and all original files and records; 65 additions produce 90 catalog books.
- [x] T017 Import confirmed new books into Calibre, normalize legacy export copies, scan Kavita and compare library/progress baselines. Clean only task-created temporary copies after verified success.

- [x] T018 Implement exact provider-ID want-to-read import for AniList, MyAnimeList, Hardcover and MangaBaka; reject title-only, conflicting, inaccessible and ambiguous matches, with compiled native tests.
- [x] T019 Add opt-in daily safe Calibre registration before export, with verified backups, isolated rehearsal, preserved original files/IDs and ambiguity holds; verify a real run.

## Account-test hardening

- [x] T020 [US4] Protect AniList and MAL removal against other account data and verify post-delete absence in `providers/sync.py` and `providers/test_sync.py`.
- [x] T021 [US4] Persist bounded provider cooldowns for HTTP and GraphQL limits and test restart behavior in `providers/transport.py` and `providers/test_gateway.py`.
- [x] T022 [US4] Apply selected-provider/action settings and native queue admission, with reread/reset holds in `independent/IndependentScrobblePolicy.cs`, `independent/independent-actions.ts` and `independent/patch_source.py`.
- [x] T023 [US4] Exercise actual native queue failure/recovery through an isolated gateway and SQLite fixture in `independent/IndependentQueueTests.cs` and `independent/test_native_queue.py`.
- [x] T024 [US4] Perform another self-review, resolve findings, build both images and verify the backed-up live rollout. Record preservation, recovery and cleanup evidence in `hardening-review.md` and `validation.md`.

- [x] T025 [US4] Extend `spec.md`, `plan.md`, `data-model.md`, `research.md`, `contracts/gateway.md`, `quickstart.md` and the requirements checklist for FR-014–018. Record implementation-time history and keep genuine-account gates open.

T020–023 evidence: 135 provider tests and 16 independent tests pass without skips. The latter includes 11 compiled native queue/wire cases and the shared native/frontend action-policy matrix. T024 evidence is recorded in `hardening-review.md`: isolated restored-state startup and live preservation pass for both images.

- [ ] T026 [US1] Verify full requested ComicBookRoundup discovery/review coverage. `providers/cbr.py` currently has partial publisher coverage and bounded enrichment. Record unavailable access explicitly in `validation.md`.

## Recovery and storage follow-up

- [x] T027 [US4] Retain independent pending events during credential removal in `independent/patch_source.py` and verify reconnection in `IndependentQueueTests.cs`.
- [x] T028 [US4] Persist authenticated creation capabilities in `IndependentProvider.cs` and verify cold restart/outage, key/origin mismatch and corruption.
- [x] T029 [US4] Bound cache and receipt storage in `providers/transport.py`, reserve protected capacity in `providers/sync.py` and verify retention/admission with small-limit fixtures.
- [x] T030 [US4] Review fixes, run focused and repository gates, build both images and verify stopped backups, restored startup and live preservation. Update validation/review and the primary-checkout spec copy.
