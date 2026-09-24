# Feature Specification: Mylar workflow controls

**Feature Branch**: `feat/mylar-workflow-controls`

**Created**: 2026-09-24

**Status**: Implemented; delivery verification pending

**Input**: Implement the five recommended Mylar additions systematically: persistent
activity/search history, queued DDL-to-NZB handoff, cooldown-aware health, guided
ambiguous-import matching with scoped aliases, and automatic intake throttling.

## User Scenarios & Testing

### User Story 1 - Follow an issue through processing (Priority: P1)

An operator sees timestamped search, provider, download, conversion, tagging and
confirmed-library observations in one Activity view, linked from Manage and Queues.

**Independent Test**: An isolated search/processing run produces a filterable trail
that survives a restart. Incomplete observations never claim a confirmed import.

**Acceptance Scenarios**:

1. Given an issue search, when providers are tried, the view shows the provider,
   result or failure category and any known next retry time without URLs or secrets.
2. Given processing events, when the service restarts, bounded history remains.
3. Given a failed refresh, the previous results stay visible with a stale warning.

### User Story 2 - Switch a waiting DDL issue to NZB (Priority: P1)

An operator can request an NZB-only replacement for one inactive single-issue DDL
item. Optional automatic handoff uses a configurable waiting threshold.

**Independent Test**: Competing DDL and handoff claims admit only one owner. No
result restores the original queue entry. An uncertain send stays held for review.

**Acceptance Scenarios**:

1. Given eligible queued work, a confirmed NZB acceptance holds the original DDL
   release and retains partial files and history.
2. Given active downloads, packs, duplicate releases, pending processing or already
   downloaded issues, the request is rejected with an actionable explanation.
3. Given a restart or lost downloader response during dispatch, no second send
   occurs automatically. The operator sees that reconciliation is required.

### User Story 3 - Understand expected waits and real stalls (Priority: P1)

An operator sees provider cooldown deadlines separately from worker failures.

**Independent Test**: Simulated clocks verify cooldown wait, expiry grace, active
transfer stalls and an absolute limit on repeated cooldown extensions.

**Acceptance Scenarios**:

1. Given only cooling queued providers and no active transfer, health explains the
   expected wait and next retry rather than declaring a frozen worker.
2. Given a dead worker, expiry without recovery, or an extended outage, Docker and
   Uptime Kuma still receive a failing health result.

### User Story 4 - Resolve ambiguous imports (Priority: P2)

Import problems offers candidate issues with title, year, issue number and matching
or conflicting evidence. Selection requires explicit confirmation. An optional
alias has an exact source-series and series-start-year scope and can be disabled.

**Independent Test**: Two same-named source files have separate identities. A stale
or changed source cannot be submitted. Repeated requests stage at most one copy.

**Acceptance Scenarios**:

1. Given an unmatched supported archive, the user reviews candidates, selects an
   issue, and sees queued, submitted, review or confirmed status accurately.
2. Given a changed file, unsafe path, active download or uncertain prior receipt,
   worker submission is refused and the original remains intact.
3. Given a confirmed successful choice with explicit series-year evidence, an
   enabled scoped alias can resolve later issues only when exactly one issue fits.
4. Given hostile input, unauthenticated requests or missing CSRF tokens, no changes
   occur and no private paths or credentials reach the browser.

### User Story 5 - Keep intake within processing capacity (Priority: P2)

New searches and snatches pause when post-processing reaches a high watermark or
available storage drops below a minimum. They resume below a lower watermark and
a higher free-space threshold. Existing transfers and processing can drain.

**Independent Test**: Fixture queue depths and disk readings cross both thresholds
without oscillation, dropped requests, failed-release marking or retry consumption.

**Acceptance Scenarios**:

1. Given throttled intake, Activity explains the cause and current thresholds.
2. Given cleared pressure, queued searches resume without operator intervention.
3. Given a missing/unreadable configured destination, intake waits and reports the
   storage problem without creating a replacement directory.

### Edge Cases

- Concurrent UI requests, worker starts, search dispatch and service restart.
- Corrupt state, bounded retention, excessive reports and malformed identifiers.
- Annuals, packs, specials, source collisions, symlinks and ambiguous acceptance.
- Provider cooldown extensions, no enabled NZB provider, healthy independent DDL.
- Queue growth during refresh, missing mounts and changed source fingerprints.

## Requirements

### Functional Requirements

- **FR-001**: Persist and filter a bounded, non-secret activity history.
- **FR-002**: Reserve handoff ownership before external work and recheck at dispatch.
- **FR-003**: Keep ambiguous sends held for review across restarts.
- **FR-004**: Preserve native provider filtering, pacing and existing active work.
- **FR-005**: Distinguish expected cooldowns from dead workers and prolonged outages.
- **FR-006**: Require authenticated, CSRF-protected POSTs for UI mutations.
- **FR-007**: Bind guided selections to a worker-owned file identity and current version.
- **FR-008**: Preserve source archives and existing submission receipts.
- **FR-009**: Keep aliases exact, reviewable, disableable and inactive until import confirmation.
- **FR-010**: Throttle new intake with hysteresis and visible reasons, preserving queued work.
- **FR-011**: Reuse existing private state volumes, primary-key worker API and ingress.
- **FR-012**: Test state transitions, races, restart recovery and browser actions in fixtures.
- **FR-013**: Publish tested images and deploy only after verified backups and isolated restores.

### Key Entities

Issue activity, handoff reservation, guided proposal, import command, scoped alias,
intake policy and health observations. None accepts browser-supplied filesystem paths.

## Success Criteria

- **SC-001**: All five user stories pass their fixture and interface acceptance cases.
- **SC-002**: Duplicate/restarted handoff and import requests cause no repeated external submission.
- **SC-003**: History survives restart, and each response contains at most 100 events.
- **SC-004**: Queue and storage thresholds pause/resume intake without changing saved provider order.
- **SC-005**: Live rollout preserves original database IDs and library hashes, returns
  service/monitor health to UP, and removes only verified operation backups.

## Assumptions

- History retains at most 5,000 events and 30 days; observing existing work is not a backfill.
- Automatic handoff is opt-in, initially two hours, one eligible issue per scheduler cycle.
- Intake defaults to 50 pending processing items, resumes at 20, and uses 5/8 GiB
  free-space stop/resume thresholds. Operators can adjust these in Activity settings.
- Cooldown expiry allows two minutes to wake; one hour without useful progress still alerts.
- Guided matching reuses the optional maintenance worker and only stages validated
  CBZ/CBR archives. Other formats continue to require conversion before submission.
- No additional download or post-processing concurrency is introduced.
