# Feature Specification: Completed comic reader scans

**Feature Branch**: `codex/komga-completed-addition-scans`

**Created**: 2026-09-29

**Status**: Implemented; delivery and live acceptance pending

**Input**: Trigger Komga library discovery after new comics finish downloading, normalization, tagging and placement. Batch five to ten additions if individual scans would add unnecessary I/O. Retain scheduled scans.

## User Scenarios & Testing

### User Story 1 - Discover completed additions (Priority: P1)

Newly completed comics become visible in the reader without a manual library scan.

**Independent Test**: Finish five new comics and observe one scan request for their library.

**Acceptance Scenarios**:

1. Given a stable existing library, when five new comics have completed all processing, request one scan for each affected library.
2. Given a downloaded comic still converting, tagging, awaiting recovery or missing metadata, do not count it until processing is complete.
3. Given fewer than five ready additions, request their scan after five minutes at the next eligible worker poll.

### User Story 2 - Bound scan overhead (Priority: P2)

Operators choose the batch size and timing while preserving scheduled scans.

**Independent Test**: Simulate repeated arrivals, restarts and reader failures with a controlled clock.

**Acceptance Scenarios**:

1. Never request additional scans more frequently than the configured minimum interval.
2. A restart retains pending additions and request pacing; an unavailable reader does not discard them.
3. Initial activation baselines the existing catalog without replaying old books or reading every existing archive.
4. A scan affects only libraries containing completed additions; scheduled scans remain unchanged.

### Edge Cases

Missing or linked paths, malformed ComicInfo, changed files, unresolved tagging receipts, deleted annuals, ambiguous catalog ownership, lost API acknowledgments, disabled settings and unavailable library roots retain safe behavior. Failed notification cannot block conversion recovery or hold a writer lock across reader requests.

## Requirements

- **FR-001**: Count only newly observed downloaded/archived catalog files that are stable CBZs with readable root ComicInfo and no outstanding conversion/tagging work.
- **FR-002**: Default to disabled in portable examples. Enabling requires existing Mylar integration and shared writer coordination.
- **FR-003**: Default batch size is 5, maximum wait is 300 seconds, and minimum request interval is 120 seconds. All are configurable positive bounded integers.
- **FR-004**: Persist pending additions and pacing in the normalizer's existing private state. Dedupe repeated observations and do not replay the initial library.
- **FR-005**: Keep per-cycle archive inspection bounded to new/pending files and central-directory/ComicInfo reads. Do not hash or decompress existing image pages for notification.
- **FR-006**: Retain failed notifications for paced retry and expose counts/outcomes in worker status. Preserve all media and existing scan schedules.
- **FR-007**: Update only the normalizer service. Verify its backup, isolated restore, app/media preservation and uninterrupted Mylar, Komga and NZBGet uptime.

### Key Entities

Completed addition: unique catalog owner and final library path.
Scan batch: ready additions awaiting reader discovery.
Baseline: catalog files already present when integration is first enabled.
Scan policy: opt-in, batch size, maximum wait and minimum interval.

## Success Criteria

- **SC-001**: Five completed additions produce one request per affected library at the next eligible poll.
- **SC-002**: Smaller ready batches request discovery within five minutes plus one successful eligible poll.
- **SC-003**: No premature counts in conversion/tagging/recovery fixtures and no media mutation by the notifier.
- **SC-004**: Restart and connection-failure fixtures lose no pending notifications, preserve pacing and avoid initial archive reads.
- **SC-005**: Live configuration, worker health, preserved media and a scoped accepted scan are verified before temporary backups are removed.

## Assumptions

Mylar and Komga see matching absolute library paths. This integration covers catalog-tracked issues and non-deleted annuals; supplemental files remain covered by existing scans. Existing recovery scans and converted-book metadata refresh are independent. The library readiness check establishes processing completion, not a second full archive-integrity audit. The worker poll and writer availability bound notification timing.
