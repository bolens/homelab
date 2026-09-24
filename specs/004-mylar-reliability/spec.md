# Feature Specification: Comic download reliability

**Created**: 2026-09-24

**Status**: Implemented and verified

**Input**: Implement ongoing queue alerts, failed-download recovery, verified cleanup,
corrupt-file quarantine, and upgrade checks. Show alerts in Uptime Kuma and container health.

## User Scenarios & Testing

### User Story 1 - Notice stopped processing (Priority: P1)

The operator receives a warning when enabled workers stop or queued work makes no progress.

**Independent Test**: Simulate a dead worker and a stalled backlog, then restored progress.

**Acceptance Scenarios**:

1. An enabled dead worker becomes unhealthy within three health-check intervals.
2. A backlog without progress for 15 minutes becomes unhealthy; renewed progress clears it.
3. Idle queues remain healthy. Warnings appear in Uptime Kuma with existing notifications.

### User Story 2 - Recover failed downloads (Priority: P1)

Failed releases are marked failed and replacement searches run without manual intervention.

**Independent Test**: Verify automatic failure handling and existing downloader integrity checks.

**Acceptance Scenarios**:

1. Mylar's supported failure workflow rejects known failed releases and searches again.
2. Downloader CRC checking and automatic parity repair remain enabled.
3. A corrupt completed archive or cached DDL archive is quarantined with a verified copy and failure receipt.
4. An unambiguous issue match can request a replacement once; ambiguous matches are reported.

### User Story 3 - Clean completed downloads safely (Priority: P1)

Completed duplicates are removed only when their original content exists in the library.

**Independent Test**: Compare real archives with added library metadata and changed pages.

**Acceptance Scenarios**:

1. Matching page names, order, hashes, and retained source sidecars permit cleanup.
2. Different scans, changing files, missing mounts, symlinks, and ambiguous evidence prevent deletion.
3. Restarts resume quarantine and cleanup without deleting changed sources or repeating retries.
4. Cleanup avoids active post-processing and waits for files to stabilize.

### User Story 4 - Check upgrades before deployment (Priority: P2)

An upgrade is rejected when the compatibility patches or recovery behavior no longer work.

**Independent Test**: Run the gate against the deployed image and a deliberately incompatible fixture.

**Acceptance Scenarios**:

1. Tests run against source from the candidate image in an isolated environment.
2. Source drift, dead-worker detection, timeouts, and unsafe cleanup failures block the gate.
3. The gate never mounts live configuration, accesses live data, or deploys a service.

### Edge Cases

- Long downloads progress without finishing, disabled queues, temporary API outages.
- A source changes after validation or after a quarantine copy is written.
- Archive limits or unavailable decoders are not mistaken for corrupt data.
- Replacement requests time out after acceptance; no blind duplicate submission.

## Requirements

- **FR-001**: Monitor worker liveness and backlog progress, with persistent observations.
- **FR-002**: Connect health warnings to existing Uptime Kuma notifications.
- **FR-003**: Enable supported failure handling without widening downloader credentials access.
- **FR-004**: Verify original content before removing completed duplicates.
- **FR-005**: Keep corrupt files recoverable outside scanned download and library directories.
- **FR-006**: Keep credentials private and add no public ports or Docker write access.
- **FR-007**: Provide a repeatable candidate-image validation gate.
- **FR-008**: Verify backups, preservation, and behavior around live updates; remove temporary backups after success.

## Success Criteria

- **SC-001**: Dead-worker, stalled-work, idle, and recovery fixtures produce the expected health states.
- **SC-002**: No unsafe cleanup fixture loses its original or changes library data.
- **SC-003**: Real duplicate cleanup and quarantine retain the promised hashes and receipts.
- **SC-004**: Live queue monitors report healthy after deployment and preserve existing monitor settings.
- **SC-005**: The deployed image passes the upgrade gate and an incompatible fixture fails it.

## Assumptions

Quarantine has no automatic expiry. New remote sources are not guaranteed to exist.
Alerts reuse configured notification destinations. Routine service restarts are not a recovery policy.
