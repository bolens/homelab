# Feature Specification: DDL mirror failover

**Feature Branch**: `codex/ddl-mirror-priority`
**Created**: 2026-09-29
**Status**: Implemented and deployed
**Input**: Retry failed downloads immediately on another mirror with queue priority, and check queued releases for available mirrors when every selected provider is cooling down.

This specification records the expanded scope during implementation. Delivery and live acceptance are recorded in tasks.md.

## User Scenarios & Testing

### User Story 1 - Continue a failed release first (Priority: P1)

A failed download immediately looks for another available mirror. Its replacement runs ahead of ordinary queue preferences.

**Independent Test**: Fail Main with a healthy Mirror available. Verify Mirror is selected and admitted before a newer single, with the original attempt count retained.

**Acceptance Scenarios**:
1. A failed Main download selects healthy Mirror without skipping it because of its label.
2. Cooling mirrors are bypassed when an available alternative exists.
3. Exhausted mirrors or attempt budgets do not create endless retries.
4. If every remaining mirror is cooling, retain the queued release until admission becomes possible.

### User Story 2 - Make progress during queue-wide cooldown (Priority: P1)

When all selected providers are cooling, Mylar checks releases in the configured execution order for mirrors that can download now.

**Independent Test**: Queue two cooling releases. The first has no available mirror and the next does. Verify checks advance in order and only the second replacement becomes eligible.

**Acceptance Scenarios**:
1. Checks follow pack/single and age preferences, including explicit priority.
2. A replacement retains the release identity and appears next without a duplicate pending entry.
3. Pausing the queue prevents both discovery checks and transfer admission.
4. Repeated misses and network errors are paced and do not spend transfer attempts.

### User Story 3 - Preserve operator decisions (Priority: P1)

Removing a release or handing it to NZB during lookup must take precedence over the lookup result.

**Independent Test**: Remove or hand off the queued record during mirror discovery. Verify it is neither recreated nor reset to Queued.

### Edge Cases

Restart, mirror lookup failures, every mirror exhausted, cooling expiration, changed release links, split pack identifiers, changed pack layout, issue ownership changes and provider label aliases.

## Requirements

- **FR-001**: Discover an alternative immediately after a transfer failure, within the existing six-attempt budget.
- **FR-002**: Prioritize the selected replacement ahead of normal ordering while preserving pause, cooldown and intake constraints.
- **FR-003**: Probe cooling releases in execution order only when no queued transfer is eligible. Check at most one release every five seconds and repeat an unchanged release no sooner than five minutes.
- **FR-004**: Keep actual failed mirrors distinct from temporarily cooling mirrors. Retain failure history and priority across restart. Explicit manual restart clears failure history.
- **FR-005**: Never overwrite concurrent removal, changed release identity or NZB handoff. Do not invent parent-to-child pack changes during mirror replacement.
- **FR-006**: Keep queue-order display consistent with admission order and record useful discovery outcomes without exposing URLs or credentials.

### Key Entities

Queued release, selected mirror, failed-provider history, provider cooldown, retry priority, paced discovery observation and issue ownership.

## Success Criteria

- Every deterministic Main/Mirror failover case selects the healthy mirror before ordinary queued releases.
- Every cooldown test respects configured ordering and pacing without spending transfer attempts.
- Cancellation and handoff tests leave operator decisions intact.
- Native-parser, image, repository and live preservation checks pass before rollout is complete.

## Assumptions

The existing single Mylar DDL worker owns automatic downloads. External DDL sources and JDownloader retain their current behavior. No new ports, mounts, credentials or dependencies are required. Only Mylar may restart for deployment. Back up and restore-test application state, verify the library in place, and retain backups on inconclusive preservation. No real power-loss test.
