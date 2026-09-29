# Feature Specification: Converted comic tagging

**Feature Branch**: `codex/converted-comic-tagging`
**Created**: 2026-09-29
**Status**: Ready for implementation
**Input**: Automatically queue metadata tagging after normalizer rescans.

## User Scenarios & Testing

### User Story 1 - Finish metadata after conversion (Priority: P1)

A verified converted comic receives missing ComicInfo metadata without manual retagging.
This closes the Modern tagger's CBZ-only import gap.
**Independent Test**: Convert a disposable archive, rescan it into the catalog, and observe one verified tag result with identical page bytes.

1. Given a completed conversion and a unique downloaded issue, when its rescan updates the catalog, then Mylar queues and tags that exact CBZ.
2. Given a delayed rescan, when the handoff arrives first, then the job waits without guessing from filenames.
3. Given disabled metadata or Legacy selected, then the job waits for supported settings without changing preferences or running another backend.
4. Given existing ComicInfo, then the automatic follow-up preserves it without repeating tagging.

### User Story 2 - Recover and explain pending work (Priority: P2)

The operator can see conversion-tagging work and interruptions do not lose or repeat successful publication.
**Independent Test**: Repeat notifications and simulate interruption after publication, then verify one publication and a durable completed status.

1. Given a failed notification, then it remains retryable without blocking other completed notifications.
2. Given a restarted Mylar worker, then queued work resumes and a committed publication is reconciled without another lookup or tag.
3. Given ambiguous catalog ownership, replaced files, or exhausted retries, then status requests review without modifying media.

### Edge Cases

Annual release IDs differ from parent IDs. Extras and alternate files not uniquely tracked must not acquire guessed issue metadata. Invalid payloads, symlinks, traversal, stale hashes, unsupported policies and missing mounts fail closed. Tests simulate interruption only, never real power loss.

## Requirements

- **FR-001**: Preserve the existing series rescan and admit a durable tagging request after its acceptance.
- **FR-002**: Match the exact downloaded catalog location under shared writer ownership, with no filename search fallback.
- **FR-003**: Authenticate admission with the primary API key and bound all inputs. Repeat requests must share one identity.
- **FR-004**: Honor enabled metadata, ComicRack-only policy and the selected Modern backend. Legacy remains selectable. Unsupported settings retain waiting work.
- **FR-005**: Preserve pages, extras, existing metadata and supported attributes. Automatically fill missing ComicInfo only.
- **FR-006**: Persist request, retry and publication identity across restart, and recover before retrying mutation.
- **FR-007**: Display bounded filename-only job status in Post-processing. Do not expose private paths, credentials or raw errors.
- **FR-008**: Keep API handling fast, serialize tagging with native post-processing, and bound retries.
- **FR-009**: Require explicit normalizer opt-in and shared writer coordination. Older installations retain rescan-only behavior.
- **FR-010**: Validate with disposable regression fixtures and an authorized bounded live canary, verified application/affected-file backups, and preservation checks.

### Key Entities

- Conversion receipt: verified output path and digest plus durable pending notification.
- Tagging job: conversion identity, exact catalog identity, phase, retry schedule, publication token and result.

## Success Criteria

- **SC-001**: A supported uniquely tracked conversion with no metadata reaches verified tagging completion without manual intervention.
- **SC-002**: Duplicate delivery and simulated restart after publication produce zero duplicate publications.
- **SC-003**: Ambiguous, changed and unsupported inputs cause zero unintended media changes.
- **SC-004**: Pending or completed tagging is visible after browser refresh and service restart.
- **SC-005**: NZBGet and Komga remain running throughout deployment.

## Assumptions

The installed Modern backend is the target. Automatic Legacy in-place publication is outside this feature because it lacks the verified receipt contract. Existing metadata is retained regardless of manual overwrite preference. No new metadata lookup provider, public route, mount or library-wide retag is introduced. The operator will trigger a Komga metadata rescan after tagging completes, as explicitly requested during implementation.
