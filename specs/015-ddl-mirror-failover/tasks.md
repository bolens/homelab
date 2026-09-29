# Tasks

- [x] T001 Trace native failure, discovery, queue selection and handoff boundaries.
- [x] T002 Implement immediate mirror priority and queue-order cooldown discovery.
- [x] T003 Exercise native labels, cancellation/handoff, attempts, pause, restart and pacing with isolated regressions.
- [x] T004 Reconcile independent reviews; pass final image and repository gates.
- [ ] T005 Merge, publish GHCR, synchronize the authorized mirror and clean completed branches.
- [ ] T006 Deploy Mylar alone with verified application backup/restore, idle admission, behavior/data/uptime checks and backup cleanup.

## Evidence

Final focused suite: 29 tests passed, including real native HTML parsing without network access. Independent review identified concurrent handoff/cancellation overwrite and the inherited Main/Mirror label ambiguity; guards and regressions address both. Both independent reviews are complete with no remaining actionable findings. Stale caller ownership and cancelled-record retention were also fixed and tested. The candidate image gate, make validate and make ci-local passed. Native DBConnection.action returns the SQLite cursor required by conditional-update rowcount checks. Publication and live delivery remain pending. No live provider failures have been induced.
