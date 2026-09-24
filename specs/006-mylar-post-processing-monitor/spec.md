# Feature Specification: Mylar post-processing monitor

**Created**: 2026-09-24

**Status**: Accepted for implementation

**Input**: Add a page to monitor the post-processing queue and status, linked from appropriate management pages.

## User Scenarios & Testing

### User Story 1 - See current processing work (Priority: P1)

Operators can distinguish idle, active, disabled, blocked, and unavailable processing,
see waiting items, and determine how long observed work has been running.

**Independent Test**: Present idle, queued, active, and unavailable worker states.

**Acceptance Scenarios**:

1. The page shows worker availability, queue depth, active work, and elapsed time.
2. Waiting entries are displayed without removing or changing them.
3. Refreshing data preserves table navigation and clearly marks failed or stale updates.
4. Unavailable progress information is labeled rather than replaced by an invented percentage.

### User Story 2 - Understand recent results (Priority: P1)

Operators can distinguish a completed processing attempt from a confirmed import and
find the existing import-problems page when an item needs attention.

**Independent Test**: Observe a successful import, an unsuccessful attempt, and a restart.

**Acceptance Scenarios**:

1. Recent observations include readable outcomes and timing.
2. Finishing a worker call alone does not claim successful import.
3. A restart clearly describes the scope of retained or reset observations.
4. File display names never expose credentials, remote URLs, or absolute paths.

### User Story 3 - Find the monitor (Priority: P2)

Operators can reach the monitor from Manage, DDL Queue Management, and Import problems,
and navigate back using controls styled consistently with those pages.

**Independent Test**: Follow each link in an authenticated browser.

**Acceptance Scenarios**:

1. Navigation reaches the correct page and uses the existing login.
2. Tables and controls initialize without JavaScript errors.
3. The monitor offers observation and navigation without destructive queue actions.

### Edge Cases

Empty queues, missing worker threads, disabled processing, concurrent queue changes,
unknown job fields, rejected filenames, exceptions, long-running work, expired login,
failed polling, no recent results, and a restart during processing.

## Requirements

- **FR-001**: Provide an authenticated, read-only monitor and current snapshots.
- **FR-002**: Show bounded waiting-item, active-item, and recent-result information.
- **FR-003**: Preserve native queue order, processing behavior, and failure propagation.
- **FR-004**: Sanitize output and escape all dynamic text.
- **FR-005**: Show freshness and stop overlapping refresh requests.
- **FR-006**: Link the monitor from the related management pages.
- **FR-007**: Validate changes before deployment and verify backup, behavior, and data preservation afterward.

## Key Entities

Worker status, waiting item, active processing observation, recent result, confirmed import,
and snapshot freshness.

## Success Criteria

- Idle, active, disabled, blocked, and unavailable fixtures produce distinct visible states.
- Queue snapshots leave entries and ordering unchanged.
- Failed attempts never appear as confirmed imports solely because a call returned.
- Browser checks verify navigation, table initialization, refresh failure handling, and escaped values.
- Image tests and repository validation pass, followed by live health and preservation checks.

## Assumptions

Use the existing Mylar login, management styling, and worker configuration. Do not change
processing concurrency, queue contents, download settings, or library files for this feature.
Bound recent observations and explain their lifetime on the page.

## Added acceptance: conversion and metadata

- Show original and output archive formats for observed tagging and conversion work.
- Distinguish added or changed metadata from unchanged, uninspected, disabled, and
  failed metadata handling. A successful tool return alone must not claim metadata
  was corrected.
- Include both Mylar tagging observations and the library normalizer's verified
  conversion receipts. Clearly label report freshness and historical gaps.
