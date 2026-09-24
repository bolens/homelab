# Tasks: Mylar workflow controls

## Setup and foundation

- [x] T001 Record source research and interface contracts in specs/009-mylar-workflow-controls/.
- [x] T002 Add private bounded events, policies and idempotent command state in stacks/mylar3/config/workflow_store.py with temporary-database regressions.
- [x] T003 Add checked integration and authenticated CSRF-protected actions in stacks/mylar3/config/patch_workflow.py and workflow.py.

## US1: Persistent activity

- [x] T004 [US1] Record native search/provider/download/processing/tagging observations in stacks/mylar3/config/workflow.py and observer modules.
- [x] T005 [US1] Add filtered, persistent Activity view and navigation in stacks/mylar3/config/workflow.html and patch_workflow.py.
- [x] T006 [US1] Prove retention, restart, redaction and refresh behavior in stacks/mylar3/config/test_workflow.py and browser fixtures.

## US2: DDL-to-NZB handoff

- [x] T007 [US2] Implement locked claim, NZB-only search scope and durable send intent in stacks/mylar3/config/workflow.py and queue_control.py.
- [x] T008 [US2] Add manual/automatic handoff controls and explicit uncertain-state review in stacks/mylar3/config/workflow.html and patch_workflow.py.
- [x] T009 [US2] Test claim races, active/pack rejection, no-result restoration and uncertain-send restart in stacks/mylar3/config/test_workflow.py.

## US3: Cooldown health

- [x] T010 [P] [US3] Implement pending-row cooldown snapshot and bounded waiting health in stacks/mylar3/config/cooldown_health.py, reliability.py and health.py.
- [x] T011 [US3] Verify expiry grace, continuous outage, active stalls and dead workers in stacks/mylar3/config/test_health.py and test_cooldown_health.py.

## US4: Guided matching

- [x] T012 [P] [US4] Implement private source proposals, evidence, command execution and exact aliases in stacks/komga/normalizer/guided_match.py and maintenance.py.
- [x] T013 [US4] Add explicit candidate confirmation, stale-version checks and alias management in stacks/mylar3/config/workflow.py, import_problems.py and import_problems.html.
- [x] T014 [US4] Test changed files, collisions, uncertain responses, source preservation and alias scope in stacks/komga/normalizer/test_guided_match.py.

## US5: Intake throttling

- [x] T015 [US5] Gate new search/dispatch with queue/storage hysteresis in stacks/mylar3/config/workflow.py and patch_workflow.py.
- [x] T016 [US5] Add settings and visible intake reasons to stacks/mylar3/config/workflow.html and verify deferred work retention in test_workflow.py.

## Integration and delivery

- [x] T017 Integrate image gates, contracts, examples, preparation and metadata in stacks/mylar3/ and stacks/komga/; regenerate affected documents.
- [x] T018 Verify both candidate images, browser flows, security boundaries and repository checks; record specs/009-mylar-workflow-controls/validation.md.
- [ ] T019 Review exact diff for correctness/privacy, pass PR checks, merge and verify GHCR/main/Pages/mirror delivery.
- [ ] T020 Back up and restore-verify live state, deploy images in order, prove data/health preservation, remove operation backups and merged task branches.

## Dependencies and execution

T002 and T003 establish shared contracts. US1 precedes handoff integration; US3 and
worker-side US4 may run in parallel in disjoint files after contract agreement.
US5 shares dispatch boundaries with US2 and follows it. Root owns shared installers,
Mylar UI, Git and integration. Each story's test tasks gate its completion. All five
stories and delivery tasks are required; there is no partial-MVP stopping point.

Parallel examples: cooldown health and guided-worker matching use separate modules
and tests. Within each story, mutations to shared files run serially. Browser checks
follow integrated backend contracts and do not mutate live comics.
