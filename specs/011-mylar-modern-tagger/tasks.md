# Tasks: Modern tagging and optional DDL transport

## Setup and foundation

- [x] T001 Verify proposal revisions and package/source contracts in `research.md`.
- [x] T002 Define preservation/rollback contracts and acceptance gates in `plan.md`, `contracts/tagger-and-transport.md` and `acceptance.md`.
- [x] T003 Implement bounded process results in `stacks/mylar3/config/tagger_runtime.py`; output <=64 KiB, deadlines 10/180 seconds, no argv in result.
- [x] T004 Implement conservative bounded XML policy in `stacks/mylar3/config/tagger_metadata.py`; XML <=256 KiB, paired arc names/numbers, explicit Volume 1.
- [x] T005 Prove R1/M1/M2 foundation cases in `test_tagger_runtime.py` and `test_tagger_metadata.py`; include real subprocesses and adversarial XML.
- [x] T006 Include foundation checks in `stacks/mylar3/config/verify_image.py`; document inactive helpers in `MODULES.md` and stack README.

## US1 - Preserved metadata

Independent test: C1/C2/P1 matrix with actual pinned CLI and generated archives.

- [x] T007 [US1] Resolve hashed target-runtime dependencies in `stacks/mylar3/requirements.txt`; document license/platform/runtime proof in `research.md`.
- [x] T008 [US1] Build isolated headless venv and final-stage native libraries in `stacks/mylar3/Dockerfile`, preserving the legacy runtime.
- [ ] T009 [US1] Implement staged archive verification and sole publication owner in `stacks/mylar3/config/tagger_adapter.py`; preserve pages, comments, sidecars and permissions.
  `tagger_archive.py` now implements the verification/reconciliation component.
  `tagger_adapter.py` adds an inactive publication owner and versioned recovery
  receipts. Native caller ownership, other-writer coordination and live filesystem
  acceptance remain pending before this task can close.
- [ ] T010 [US1] Add real CLI and archive cases C1/C2/P1 in `stacks/mylar3/config/test_modern_tagger.py`, including actual observed version banner and error behavior.
  CLI/version, generated archive preservation and legacy isolation cases pass.
  Reconciled XML is now written into a new CBZ and read back with content/permission
  checks. Native publication and the complete failure/recovery matrix remain pending.
- [ ] T011 [US1] Wire additive backend choice and native/manual/annual routing; cover N1/N2 and update every affected stack contract.
  `patch_tagger_handoff.py` installs checked manual ownership and automatic rejection
  guards. `mylar.tagger_handoff` is the sole native result identity. Legacy temporary
  paths retain their behavior. The inactive service now provides bounded ComicVine
  lookup, manual in-place results, automatic disposable outputs, no-overwrite policy
  and exact backend dispatch. The native settings selector now persists a Legacy
  default and visibly gates Modern availability. Server validation precedes changes,
  and the native entry point captures the choice once per job. Modern routing,
  annual caller identity and remaining native writer coverage remain pending.
  Shared flock admission and durable normalizer recovery fences now cover complete
  post-processing/manual tagging and opt-in normalizer cycles. Live coordination
  rollout, modern recovery ownership and canary checks remain pending.

## US2 - Failure recovery and observability

Independent test: C3/C4/N3/L1 failures, recovery and old-image rollback.

- [ ] T012 [US2] Add versioned durable publication intent and restart reconciliation in `tagger_adapter.py`; test source races and crash boundaries in `test_modern_tagger.py`.
  The standalone publisher has real-process crash tests before/after exchange,
  conflict retention, token serialization and historical replay coverage. The streaming
  startup recovery API now skips completed history and reports busy/invalid receipts.
  Native startup wiring and native writer exclusion remain pending.
- [ ] T013 [US2] Connect verified added/updated/unchanged/failed/timed-out/unsupported results to `archive_monitor.py`, with tests for all monitor states.
  The native observer now consumes verified Published results with tests for all
  outcomes. Active modern producer routing and live UI acceptance remain pending.
- [ ] T014 [US2] Verify old/new image state compatibility and scoped canary rollback, record evidence in `validation.md`. Keep legacy selectable.

## US3 - Optional DDL discovery

Independent test: D1/D4 dual-backend local HTTP/proxy/TLS fixtures. D2/D3 gate full streaming separately.

- [ ] T015 [US3] Lock optional curl dependencies and add lazy discovery session adapter in `stacks/mylar3/config/ddl_transport.py`; normalize exceptions and cleanup without added retries.
- [ ] T016 [US3] Add server-validated opt-in discovery choice and next-session switching in native adapter/UI; keep requests archive transfers and document availability.
- [ ] T017 [US3] Prove D1/D4 in `stacks/mylar3/config/test_ddl_transport.py`, with the current requests tests unchanged.
- [ ] T018 [US3] Evaluate full curl streaming with bounded backpressure, memory/cancellation and D2/D3 tests in `test_ddl_transport.py`. Do not expose this mode if proof fails.

## Delivery

- [x] T019 Audit final increment and run focused tests, full candidate image gate and `make ci-local`; record completed versus pending gates in `validation.md`.
- [ ] T020 Publish the reviewed increment through PR/GHCR; activate only capabilities with completed gates, follow verified backup/restore/canary workflow in `plan.md`.

## Dependencies and implementation strategy

T001/T002 precede T003-T006. First increment is T003-T006 only, leaving native
behavior unchanged. T007/T008 precede T009-T011. T012 must be complete before native
activation, with T013/T014 completing US2. US3 is independently deployable after
T015-T017. T018 is an evaluation option, not an implied activation requirement.
T019/T020 apply to each deliverable increment and do not mark unfinished gates done.

Parallel opportunities: runtime and metadata helper tests can be developed separately.
Dependency packaging and transport fixture research can run independently after the
contracts are fixed. Archive publication and native integration share ownership and
must be sequenced. No agent may change live services during fixture work.
