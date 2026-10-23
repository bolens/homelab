# Feature Specification: ErsatzTV library channels

**Created**: 2026-10-19
**Status**: In progress
**Input**: Deploy ErsatzTV, provide a tunnel management hostname with Access when native form login is unavailable, and meet maintained stack standards.

## User Scenarios & Testing

### User Story 1 - Protected management (Priority: P1)
The operator can manage ErsatzTV through a valid HTTPS hostname after authentication.
**Independent Test**: Request the hostname without a session and verify login is required.
**Acceptance Scenarios**:
1. Given no native form login, an anonymous visitor must authenticate through the existing identity policy before reaching management.
2. Given a direct origin request outside the intended connector path, access is refused.

### User Story 2 - Library television (Priority: P2)
The operator watches scheduled library content in Plex through Dispatcharr.
**Independent Test**: Confirm one populated channel, matching guide entries, and actual media playback through the integration.
**Acceptance Scenarios**:
1. Existing movies and TV remain unchanged after library discovery.
2. At least one station has a populated schedule and playable content.
3. Existing Dispatcharr channels, Plex DVR identities and recording rules remain intact.

### User Story 3 - Maintainable deployment (Priority: P2)
The operator can prepare, validate, back up and recover the stack using its documentation.
**Independent Test**: Prepare an isolated fixture twice and run required validators.
**Acceptance Scenarios**:
1. A missing media mount refuses preparation without creating a replacement directory.
2. Preparation preserves existing configuration and never starts containers.

### Edge Cases
- Missing remote media filesystem refuses deployment.
- Missing cloud permissions leave public access disabled until the protection is verifiable.
- An empty library is reported explicitly rather than counted as successful playback.

## Requirements

### Functional Requirements
- **FR-001**: Protect public management with authentication, using Access when no form login exists.
- **FR-002**: Preserve private playback connectivity independently of browser authentication.
- **FR-003**: Preserve existing libraries, channels, recording rules and service settings.
- **FR-004**: Verify affected configuration and application-state backups through isolated restoration before modifying existing services.
- **FR-005**: Maintain matching deployment, environment, preparation, ingress, metadata and documentation contracts.
- **FR-006**: Use existing media read-only and require the intended filesystem before deployment.
- **FR-007**: Provide morning cartoon programming drawn from available animation, with explicit schedule and content-rating choices.
- **FR-008**: Provide seasonal station programming for the current Halloween season and available holiday content.
- **FR-009**: Use the newest supported stable application and streaming engine, and verify container GPU encoding on the available hardware.
- **FR-010**: Give every created station fitting artwork that remains available in the exported guide.
- **FR-011**: Expand the initial lineup with additional populated genre stations after validating the initial channels.
- **FR-012**: Balance Morning Cartoons by show while retaining its episodes-only
  eligibility and individual programme guide entries. Preserve Clare's exact
  personal collection references and both nighttime stations' quiet presentation.
- **FR-013**: Provide restrained station presentation using existing artwork:
  short silent IDs on selected daytime/movie stations and intermittent corner
  logos outside nighttime stations. Preserve source media and guide identities.
- **FR-014**: Add recurring seasonal weekend specials to Movie Night with
  automatic return to its normal schedule. Use existing scoped seasonal rules,
  retain individual film listings, and verify calendar selection and playback.
  Add trailers only when suitable local trailer assets are available.
- **FR-015**: Extend the existing host maintenance workflow with private
  reproducible channel recipes, native/Dispatcharr/Plex programme comparisons,
  strict personal-station checks, drift metrics and alerts. Checks must not
  reset schedules or alter recordings. Reconciliation must refuse active or
  scheduled recording conflicts and active viewing before changing filters.
- **FR-016**: Include ErsatzTV's consistent SQLite snapshot and required
  configuration/artwork/ID assets in verified daily backup generations without
  interrupting playback. Prove recovery on a disconnected application restore.
- **FR-017**: Enable tested loudness normalization and English forced subtitles
  with Next burn-in delivery, retaining the NVENC/codec choices. Verify encoded
  audio levels and subtitle rendering as well as ordinary playback.
- **FR-018**: Provide a rolling seven-day playout and guide, disable periodic
  full resets, preserve committed airtimes and DVR identities/rules, and verify
  programme transitions, simultaneous viewers and stream cleanup.

### Key Entities
- Station: stable identity, number, content rule and schedule.
- Library: existing media and descriptive metadata.
- Guide: scheduled programs mapped to station identities.

## Success Criteria

### Measurable Outcomes
- **SC-001**: Anonymous visitors cannot reach management through the public hostname or direct origin route.
- **SC-002**: At least one station plays library content with matching program listings.
- **SC-003**: Existing channel and recording identities remain unchanged.
- **SC-004**: Focused checks and the required repository validation pass, with optional skips recorded.

## Assumptions
- Reuse the existing tunnel, identity restrictions, reverse proxy and Plex connection.
- Start with bounded genre-based stations, without installing a recurring channel-invention job.
- Runtime addresses, credentials, account identifiers and private evidence remain outside tracked examples.


### Library-only network collections

Network-themed stations play available library media, with native Plex network
metadata and reviewed title fallbacks that catch future episodes and series.
Creator/studio stations retain directing/production boundaries and exact library
scope. Personal channel restrictions and all original station IDs remain intact.
The organized custom output range precedes the reserved multiview range.

A temporary library-only presentation must disable or hide every non-Ersatz
output without deleting its channels, stream links, profiles, sources or logos.
Plex may discard bindings absent from the tuner output. Keep those exact IPTV
bindings in the backed-up restoration manifest while verifying the complete
current custom map. Pause
quarantine mutation while the channels are retained for later work. Backups and
library-guide monitoring continue. Validate the actual visible Plex lineup and
complete programme identities after import, not only application row counts.
