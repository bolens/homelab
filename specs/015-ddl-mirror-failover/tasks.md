# Tasks

- [x] T001 Trace native failure, discovery, queue selection and handoff boundaries.
- [x] T002 Implement immediate mirror priority and queue-order cooldown discovery.
- [x] T003 Exercise native labels, cancellation/handoff, attempts, pause, restart and pacing with isolated regressions.
- [x] T004 Reconcile independent reviews; pass final image and repository gates.
- [x] T005 Merge, publish GHCR, synchronize the authorized mirror and clean completed branches.
- [x] T006 Deploy Mylar alone with verified application backup/restore, idle admission, behavior/data/uptime checks and backup cleanup.

## Evidence

Final focused suite: 29 tests passed, including real native HTML parsing without network access. Independent review identified concurrent handoff/cancellation overwrite and the inherited Main/Mirror label ambiguity; guards and regressions address both. Both independent reviews are complete with no remaining actionable findings. Stale caller ownership and cancelled-record retention were also fixed and tested. The candidate image gate, make validate and make ci-local passed. Native DBConnection.action returns the SQLite cursor required by conditional-update rowcount checks. Publication and live delivery passed as recorded below. No live provider failures have been induced.

PR #163 merged as `d314cd28885f0f9a29fe1f52be81fbe1b6779d4b` from reviewed head `6519511a35616907281cc88d1aed753e9e0877c7`. All final-head and post-merge checks passed, including Pages and GHCR publication. The final front-priority adjustment also passed independent review and the local image gate. GitHub, local main and the authorized mirror were synchronized; the completed feature branch was removed.

Published image `sha256:f7040af1c37d68e418874a24d414ac491b36f4b73065fade4500ea3ae15cebb6` passed its isolated installed-image gate and was deployed to Mylar alone after admitted work drained. Application backup and isolated restore verification passed. Final database integrity, baseline catalog IDs/statuses/locations and existing library file inventory passed. Authenticated queue UI loaded without errors. Original workflow policy was restored. Komga, NZBGet, the normalizer and Uptime Kuma retained container IDs and start times. Temporary operation backups were removed after verification. No library copy, real power-loss test or induced live provider failure was performed.
