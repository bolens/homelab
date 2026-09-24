# Feature Specification: Mylar queue control and import visibility

**Created**: 2026-09-24

**Status**: Implemented and verified

**Input**: Implement the suggested queue visibility, provider cooldowns, bounded retries,
automatic restart recovery, stricter completion checks, and import-problems view.
Investigate older-issue DDL searches before changing matching rules.

## User Scenarios & Testing

### User Story 1 - Understand progress (Priority: P1)

Operators can distinguish downloading, retrying, cooling down, and stalled work.

**Independent Test**: Observe a growing transfer, an unchanged transfer, and repeated failures.

**Acceptance Scenarios**:

1. Queue rows show received bytes, recent speed, time since progress, and a safe retry reason.
2. Retry activity without useful progress cannot indefinitely clear stall warnings.
3. Failed providers wait before another attempt while other eligible items continue.
4. A release stops after a bounded number of attempts, including across restarts.

### User Story 2 - Recover without losing work (Priority: P1)

An interrupted service restores eligible queue items once and preserves partial downloads.

**Independent Test**: Restart with queued, interrupted, completed, and duplicate records.

**Acceptance Scenarios**:

1. Eligible records are queued once, stale active states are cleared, and completed records stay completed.
2. Resume requires matching saved bytes and a compatible server response.
3. Incomplete transfers remain separate from files offered to post-processing.
4. A truncated or invalid archive never becomes a completed download.

### User Story 3 - Find import problems (Priority: P1)

Operators can find completed files that remain unimported, ambiguous matches, and quarantines.

**Independent Test**: Present matched, unmatched, invalid, and ambiguous fixtures.

**Acceptance Scenarios**:

1. An authenticated view gives file names, reasons, and specific suggested actions.
2. Ambiguous files remain untouched and are never assigned automatically.
3. Missing or old maintenance reports are visibly identified.
4. Credentials and remote download links never appear in the report.

### User Story 4 - Verify older-issue searches (Priority: P2)

Operators receive evidence whether the reported search regression affects this installation.

**Independent Test**: Inspect query generation and compare bounded search results for wanted older issues.

**Acceptance Scenarios**:

1. Search changes require a reproduced gap and preserve issue, volume, and year validation.
2. Existing working fallback behavior is retained and regression-tested.

### Edge Cases

Unknown sizes, rate-limited providers, a server ignoring Range, expired download URLs,
missing mounts, process termination, duplicate queue entries, corrupted state, conflicting
partial files, missing maintenance reports, and a restart during post-processing.

## Requirements

- **FR-001**: Persist attempts, cooldowns, progress, and recovery state privately.
- **FR-002**: Bound retry work without dropping unrelated queued items.
- **FR-003**: Restore interrupted work without duplicate imports or discarded source bytes.
- **FR-004**: Verify transfers and archives before post-processing.
- **FR-005**: Expose import problems through existing authentication with no new public ports.
- **FR-006**: Keep provider requests bounded and retain existing search validation.
- **FR-007**: Verify isolated backups before deployment and preservation afterward.

## Key Entities

Download attempt, provider cooldown, partial transfer, completed archive, import problem,
quarantine receipt, and recovery record.

## Success Criteria

- **SC-001**: Progress, cooldown, retry exhaustion, and stall fixtures produce distinct expected states.
- **SC-002**: Restart and interrupted-transfer fixtures preserve bytes without duplicate queue entries.
- **SC-003**: Invalid and truncated archives never reach post-processing in regression tests.
- **SC-004**: Import-problem fixtures are readable, authenticated, and free of credentials.
- **SC-005**: Candidate-image and repository gates pass, then live queues and preservation checks pass.

## Assumptions

Use one native DDL worker and existing post-processing concurrency. Default to six attempts
per release and a 15-minute provider cooldown after repeated failures. Keep recovery files
until their original bytes are verified elsewhere. An unavailable search provider is an
inconclusive test, not evidence that a comic does not exist.
