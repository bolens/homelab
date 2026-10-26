# Tasks: Verified archive repair

**Current delivery requirement (2026-10-10)**: Hosted CI must pass before any further merge. The user has revoked the outage waiver; historical waivers in the linked evidence history do not authorize new exceptions. Fix failing checks while preserving their acceptance assertions.

## Current remaining work

**Updated 2026-10-26.** 17 of 22 tasks are complete. T019–T022 are delivered
implementation corrections, not additional runtime gates. Five tasks remain:
T012/T015 share one isolated forward and one distinct-fixture rollback with
feature 023 T026/T029 and the isolated portion of T027; T016–T018 own later
scoped live acceptance.

1. Complete the owning NFS/reader handoff, backup/restore, archive transition,
   factual terminal consumption and permitted resume within T012, preserving
   original identity, custody and freshness checks. Use retained failure
   evidence to distinguish an implementation defect from a correct refusal.
   Diagnose held attempts without replay or an inferred resume grant.
2. After accepted forward proof, run explicit rollback on a distinct fixture.
   Independently compare its causal source, complete native preimage and affected
   reader state. Reuse the same immutable installation when its exact inputs
   remain unchanged.
3. Record each accepted original terminal/preservation result once and link it
   from every shared task. Passing source tests, NFS readiness or reader stop
   alone cannot close T012/T015. Leave every unmet criterion open.
4. Follow T016–T018 for production backup, selected repair/import and library
   acceptance. Disposable-fixture authorization supplies no production or
   permanent-worker activation permission.

PR [#515](https://github.com/bolens/homelab/pull/515) supplies the retained
180-module native baseline and DATA precondition; the required SDK has 103
entries after PR [#521](https://github.com/bolens/homelab/pull/521).
PR [#522](https://github.com/bolens/homelab/pull/522) changes five installed native
modules for the shared phase deadline. Require its matching published image and
fresh module capture before the next isolated pair. That capture is now verified.
PR [#524](https://github.com/bolens/homelab/pull/524) delivered copied-control
roundtrips, original-provider references and the host-side selected-child mount
check. Its fresh CX operation passed that host check, stopped only its disposable
reader, then held in the installed Birth consumer: the SDK still applied its
64-row native/worker parser to the complete 73-mount child vector. The retained
child traceback identifies that exact boundary.

PR [#525](https://github.com/bolens/homelab/pull/525) delivered the shared
selected-child projection in SDK Scope, Birth and both host adapters. Its matching
image capture verifies all 180 modules and the required 103-module SDK. Fresh
checked controls and disposable bootstrap passed. A stale private readiness
input was corrected from its exact Scope and Probe sources before DB passed
SourceCohort and reached the owning Parent.

PR [#526](https://github.com/bolens/homelab/pull/526) delivered strict integer
versions 3/4 for the unchanged publication protocol. Local and hosted checks,
main publication, actual 180-module capture and the required SDK103 joins pass.
Fresh DC host controls verified all 27 outputs, and DD's disposable bootstrap
passed. DC then reached the owning Parent and stopped only its disposable reader,
but held in prebirth custody with `archive-producer-final-file`, before archive
execution. The original transient vector was not retained, so the exact changed
path in that attempt is unknown. Both archives' full9/hashes, all 24 native tables
and the original native process/config remain unchanged. Preserve DC/DD and all
prior holds without replay or inferred resume.

Independent metadata-only observation found native DATA directory changes from
SQLite journal creation/removal. A local owning phase-custody reproduction proves
a false hold when a real transaction rolls back with database bytes/full9 and
config unchanged. Correct only that live directory's prebirth identity policy,
requiring exact native/worker DATA geometry and original identity5; preserve all
other file/full9, reader/restore, source, scope and absence guards. Retain bounded
metadata on future file refusals. This independently demonstrated defect does not
identify DC's original offending path. Unchanged SDK/image proofs may be reused
only for their exact native/worker bytes; changed host controls require a fresh
checked installation and unused fixture. [Retained failure
history](evidence-history.md#prebirth-live-data-custody-hold--2026-10-26) owns the
observations. Isolated forward and distinct-fixture rollback remain within
T012/T015; neither is accepted yet.

PR [#512](https://github.com/bolens/homelab/pull/512) delivered the earlier plan
audit. Later source corrections remain work within T012, not new task plans.
Reviewed frozen source and its matching installation may be tested in an
explicitly authorized disposable operation before merge. Hosted CI still gates
merge and final delivery must join the accepted runtime evidence. Preserve
all held attempts. Superseded execution instructions belong in [evidence
history](evidence-history.md#superseded-execution-notes--2026-10-23), not this queue.

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
- [x] T019 [US3] Deliver the finite owning metadata vector and batched geometry reads described in `plan.md` and `CONTRACT-nfs-factual.md`, preserving both closure passes, sealed dispatch, original custody and failure handling. Independent hostile-callback review, source controls and actual Root/NFS benchmarks pass; PR #507 delivers this implementation. Connected acceptance belongs to T012/T015.
- [x] T020 [US3] Deliver the exact original-operation host/child namespace distinction in `plan.md`, retaining authenticated plans, Root host custody, physical child checks and final closure. Private-geometry, alias and late-mutation controls and independent review pass; PR #509 delivers the implementation. Connected acceptance belongs to T012/T015.

- [x] T021 [US3] Deliver the owner-principal mount observer in `plan.md`, lowering only the admitted findmnt child to fixed UID1000/GID1000 without supplementary groups. Identity isolation, unchanged Docker dispatch, failure/deadline controls, actual retained-directory observation and independent review pass; PR #510 delivers the implementation. Connected acceptance belongs to T012/T015.
- [x] T022 [US3] Deliver the original retention-root probe binding in `plan.md` and `CONTRACT-nfs-mount-namespace.md`, restricted to genuine original plan13 geometry with unchanged nested fixture identity and prepared/prewrite closure. Hostile-path, proof-substitution, legacy and late-change controls, complete pins, independent review and local/hosted delivery pass in PR #511. Fresh checked inputs and disposable bootstrap are verified. Forward and distinct rollback belong to T012/T015.

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

Implementation T001–T011, T013–T014 and T019–T022 is complete. Matching checked
source/install delivery precedes the shared T012/T015 runtime pair. Accepted
connected readiness and delivery precede T016 backup/rollout, T017 selected live
repair/import and T018 current-library acceptance. Feature 022 owns its later
combined pass and post-bulk idempotence. Historical diagnostics or private
experiments grant no operational completion.

## Next execution and completion evidence

Use the existing installed producer/Parent path once per fresh attempt. Static
source binding and SourceCohort precede fresh role/scope observations; the owning
120-second admission limit stays unchanged. Leave the probe parent absent for
its owning Parent to create. The Parent owns Writer, stopped-reader custody,
verified backup/restore, archive transition, factual terminal consumption and
permitted resume. A wrapper or test count supplies none of those facts.

Use the current matching host installation and SDK inputs described above for
the next unused fixture. Historical BZ channel deadlines and later held attempts
are retained in evidence history; they are not instructions to repeat an old run.
No held attempt has replay or inferred resume authority.

Forward and explicit `terminal=rollback` use distinct fixtures, requests,
baselines and original receipts. Rollback restores the causal malformed source,
not the forward fixture's repaired genesis. Verify each original terminal chain
and independently compare archives, complete native changes and affected reader
state. Preserve unknown outcomes; diagnose before any fresh correction.

One accepted pair supplies the shared isolated criteria of 023 T026/T029/T027
and 024 T012/T015. Source/install milestones are prerequisites to that pair, not
circular dependencies on whole-task completion. T015 still requires matching
source/image delivery. No isolated result creates a live import ACK or grants
production, whole-library, bulk or cleanup acceptance.

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

## Configured child source refusal — 2026-10-23

A fresh isolated attempt passes SourceCohort and reaches the owning Parent's NFS
child. The child refuses `cohort-parent-path`: the executing installed source and
the receipt's original source were projected into different control copies.
Original child logs establish that refusal before the host's subsequent vanished
PID check. The observed failure does not establish a timeout. Reader/native
original epochs remain running and the worker remains Created. Independent
post-hold comparison preserves both archives' full signatures, bytes and ZIP
members, both reader book/progress records and all six page hashes. The held
attempt and helper remain preserved without replay.

The corrective source joins exact original and installed source incarnations
before projecting the declared installed copy. Eight additional local controls
include the real child cohort consumer and the prior failure. Installation,
matching-source delivery and fresh configured forward/rollback, NFS and terminal
acceptance remain required. T012/T015 and feature 023 T026/T029 stay open.

## Configured admission hold — 2026-10-23

After PR #505 and a fresh checked installation, T passes SourceCohort and the
child's original/installed Parent path join. Its NFS child then exits before
reader stop; the wrapper omits the underlying lifecycle-admission reason. Original
scope evidence is already 199.25 seconds old at helper start, beyond the unchanged
120-second limit. This establishes a stale-input condition, not the first thrown
exception or a child-channel timeout. T and its helper remain preserved without
replay. Independent post-hold comparison preserves both archives' full signatures,
bytes and members, both reader book/progress records and six page hashes.

The source correction removes duplicate identical metadata checks within each
closure pass and retains bounded original exception-context frames. Local
benchmark counts and controls establish neither actual Root/NFS latency nor
configured forward/rollback, terminal, ACK or preservation acceptance. A fresh
checked generation remains required. T012/T015 and feature 023 T026/T029 stay open.
