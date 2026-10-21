# Feature Specification: IPTV reliability and recovery

**Feature Branch**: `codex/dispatcharr-plex-setup`

**Created**: 2026-10-19

**Status**: Implemented; acceptance evidence in validation.md

**Input**: Implement the six proposed IPTV improvements: guide coverage, backup streams, matching Plex XMLTV export, multi-day channel quarantine, recording defaults, and recovery/failure checks.

## User Scenarios & Testing

### User Story 1 - Predictable viewing and guide data (Priority: P1)

The operator browses the same selected channels in the tuner and guide, uses genuine schedules where available, and keeps unavailable schedules explicitly labeled.

**Independent Test**: Compare tuner and XMLTV channel sets, check current real programs, and decode a selected station through its configured stream chain.

**Acceptance Scenarios**:

1. Given an existing Plex DVR, when its guide export is scoped, then the tuner, DVR identity and recording rules survive and the guide includes only the selected profile.
2. Given a news-only feed, when schedules are matched, then only schedules describing that exact feed are used. An OTA affiliate's full network schedule is not substituted.
3. Given equivalent tested streams, when the primary fails, then an alternate is selected without changing the channel identity.

### User Story 2 - Reversible maintenance and useful recordings (Priority: P2)

The operator keeps channels during temporary outages and records without permanently cutting commercial footage.

**Independent Test**: Simulate failed checks on distinct days, recovery and local-news exclusions; inspect recording defaults without changing existing rules or deleting recordings.

**Acceptance Scenarios**:

1. A failed stream is quarantined before deletion, must fail on at least three distinct days, and must remain failed for at least fourteen days.
2. A recovered channel returns to its original group and eligibility; requested local-news channels remain protected.
3. New recordings receive bounded padding and retention defaults, and commercial markers preserve original footage.

### User Story 3 - Recoverable state and actionable health (Priority: P2)

The operator receives existing-stack health alerts for failed guides, recording failures, storage issues and stale verified backups.

**Independent Test**: Restore a new application-consistent backup in isolation, verify records/files and native database integrity, and inject unhealthy samples into monitoring tests.

### Edge Cases

- A missing media or backup mount must refuse writes and report failure.
- A same-day repeated check cannot count as another failed day.
- Ambiguous or mismatched guides leave the fallback intact.
- Missing monitoring or scheduler output is unhealthy, not a healthy zero.
- Backups and logs can contain credentials and remain outside Git with restricted permissions.

## Requirements

### Functional Requirements

- **FR-001**: Preserve existing users, credentials, original channel identities, DVR identities, rules and recorded media.
- **FR-002**: Use matching profile-specific HDHR and XMLTV exports.
- **FR-003**: Improve exact-feed guide coverage with legitimate sources and retain labeled fallback data when verification fails.
- **FR-004**: Link only equivalent, media-verified alternate streams and demonstrate bounded failover.
- **FR-005**: Gate permanent channel deletion on fourteen elapsed days and three distinct failed days; recovery clears failure history.
- **FR-006**: Protect requested local-news channels and preserve manual matching previews.
- **FR-007**: Configure future recording padding, bounded retention and non-destructive commercial detection without modifying existing recordings.
- **FR-008**: Schedule application-consistent database/configuration backups and verify an isolated restore before treating a backup as usable.
- **FR-009**: Monitor guide freshness, recording failures, mounted recording storage/free space, backup age and job freshness through existing monitoring.
- **FR-010**: Keep public examples portable, preparation inert and live secrets private; validate changed contracts and preservation.

### Key Entities

- Channel health history: stable channel UUID, original group/profile memberships, dated failed observations, recovery state.
- Backup receipt: successful restore time, image identity, file checksums and validated record counts.
- Guide match: exact feed identity, source, current program interval and fallback status.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Plex's tuner and XMLTV expose the same 450 selected channels with unchanged existing DVR identity.
- **SC-002**: All original physical-library records and Dispatcharr user credentials survive.
- **SC-003**: Recovery, elapsed-time, distinct-day and mount refusal cases pass fixtures.
- **SC-004**: A recurring backup has a successful isolated restore and monitoring exposes current health.
- **SC-005**: Verified guide matches and fallback gaps are reported separately, without a promised coverage count.

## Assumptions

- No provider purchase, payment or new external account is required.
- Existing monitoring receivers are reused; no new recipient or channel is created.
- Recording retention applies to future scheduled recordings and never purges existing media during setup.
- Local-news protection includes Milwaukee, Seattle, Atlanta and Minneapolis.

## Authorized follow-up: supplemental guides and organization

The operator requested additional free guide coverage and organized channels.
Check current XMLTV schedules against feed identity and region, retain existing
real mappings, and leave ambiguous or mismatched feeds on labeled fallback.
Group starter channels by genre, move US affiliates out of generic categories,
repair malformed imported display names, and use alphabetical browsing without
changing channel numbers, UUIDs, profile membership or recording rules.

## Authorized follow-up: city and network station matrix

The operator requested individual NBC, ABC, CBS and FOX news feeds for Denver,
Milwaukee, Atlanta, Seattle, Minneapolis and Sanibel/Fort Myers, plus one mosaic
per city and one per network. Preserve the existing four-city mosaic with Denver
audio. City mosaics order available verified feeds as NBC, ABC, CBS, FOX, using
the first available tile's audio. A missing public feed remains an explicit gap;
never replace an affiliate news feed with unrelated national/OTA programming.
Keep every existing standalone channel and its tuning identity. Network mosaics
use a fixed city order beginning with Denver where available and remain on
request only, within the current CPU/memory limits. Sanibel uses the regional
Fort Myers/Naples news market rather than claiming a dedicated island station.
