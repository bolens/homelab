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
- [x] T009 [US1] Implement staged archive verification and sole publication owner.
  `tagger_archive.py`, v2 `tagger_nfs.py`, native ownership and staging receipts
  preserve pages, comments, sidecars and supported permissions. T021-T023 and
  the live canary cover actual NFS publication and recovery.
- [x] T010 [US1] Add real CLI and archive cases C1/C2/P1.
  Final-image gates exercise the pinned binary, generated regular/annual/variant
  archives, metadata reconciliation, native publication and failure/recovery.
  Live canary and rollback evidence is recorded in `validation.md`.
- [ ] T011 [US1] Wire additive backend choice and native/manual/annual routing.
  Native and conversion ownership passed in T022 and live canaries. The opt-in
  activation increment retains Legacy as default and removes the static gate.
  Live settings save/reload and switching back to Legacy remain to be verified.

## US2 - Failure recovery and observability

Independent test: C3/C4/N3/L1 failures, recovery and old-image rollback.

- [x] T012 [US2] Add versioned durable publication intent and restart reconciliation in `tagger_adapter.py`; test source races and crash boundaries in `test_modern_tagger.py`.
  The standalone publisher has real-process crash tests before/after exchange,
  conflict retention, token serialization and historical replay coverage. The streaming
  startup recovery API now skips completed history and reports busy/invalid receipts.
  Native startup wiring and native writer exclusion are implemented by T022;
  live canary/rollback acceptance passed in T014/T023.
- [x] T013 [US2] Connect verified added/updated/unchanged/failed/timed-out/unsupported results to `archive_monitor.py`, with tests for all monitor states.
  The native observer now consumes verified Published results with tests for all
  outcomes. Native producer routing was verified in T022 and the live canary;
  N3 UI acceptance passed at phone/wide sizes after PR #148 corrected readable
  columns, keyboard scrolling and readiness wording. Outcome/history fixtures
  remained browser-local; global Modern activation is still separate.
- [x] T014 [US2] Verify old/new image state compatibility and scoped canary rollback, record evidence in `validation.md`. Keep legacy selectable.

## US3 - Optional DDL discovery

Independent test: D1/D4 dual-backend local HTTP/proxy/TLS fixtures. D2/D3 gate full streaming separately.

- [ ] T015 [US3] Lock optional curl dependencies and add lazy discovery session adapter in `stacks/mylar3/config/ddl_transport.py`; normalize exceptions and cleanup without added retries.
- [ ] T016 [US3] Add server-validated opt-in discovery choice and next-session switching in native adapter/UI; keep requests archive transfers and document availability.
- [ ] T017 [US3] Prove D1/D4 in `stacks/mylar3/config/test_ddl_transport.py`, with the current requests tests unchanged.
- [ ] T018 [US3] Evaluate full curl streaming with bounded backpressure, memory/cancellation and D2/D3 tests in `test_ddl_transport.py`. Do not expose this mode if proof fails.

## NFS filesystem acceptance correction

- [x] T021 Implement explicit v2 retained-inode/no-clobber publication and bounded
  ACL preservation in `tagger_nfs.py` and `tagger_attributes.py`. Preserve the v1
  exchange strategy and reject mixed-version receipts without mutation. Prove real
  process crash boundaries, competing writers, ambiguous NFS RPC results, exact ACL
  preservation and canonical handoff on disposable actual-media fixtures.
- [x] T022 Integrate v2 journal selection, startup reconciliation and scanner/writer
  admission with native routing. Prove the missing-name interval is recovered before
  other work. Cover annual identity, automatic output lifetime, and deferred worker
  refresh outside ownership. Keep Modern disabled.
- [x] T023 Complete the remaining T022 old-image rollback acceptance together with
  T014 live coordination/canary rollout. Old readers must never run against pending
  v2 publication; recover first or restore verified prior state and affected fixtures.

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
