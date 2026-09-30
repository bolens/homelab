# Validation

Repository implementation verified on 2026-09-29.

Two independent reviews covered behavior/contracts and tests/failure paths. A crash between native no-result publication and the journal update could replay a search. Startup now settles that result or holds an interrupted final search for review. A regression test covers both states. The README also now describes failed-state publication accurately.

- `test_workflow.py`: 42 passed, including exhaustion eligibility, provider filtering, no-result persistence, source changes, restart publication recovery, accepted and uncertain submissions, explicit DDL restore and existing ownership races.
- `test_workflow_nzb.py`: 8 passed.
- `test_ddl_failover.py`: 13 passed.
- `test_workflow_store.py`: 4 passed.
- `test_ddl_exhaustion.py`: 2 passed.
- `test_queue_control.py`: 12 passed.
- Native-source checks used an isolated copy of `/app/mylar3/mylar` obtained through `pkexec docker cp`. Configuration and application data were not accessed. Initial native-fixture skips were resolved by this copy. No containers were created, restarted or stopped.
- `make validate`: passed. Rendered 214 Compose stacks with zero failures. The externally generated PostHog bundle was skipped by the repository validator.
- Pages regeneration produced no tracked changes. Python compilation and `git diff --check` passed.

The full candidate-image gate and a live NZB download were not run. The implementation is local and requires image publication and deployment before affecting the running service. No live update, backup or rollback operation was performed.
