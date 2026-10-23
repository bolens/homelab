# Feature Specification: Librarr integrations

**Feature Branch**: `codex/librarr-integrations`
**Created**: 2026-10-23
**Status**: Repository implementation verified; live deployment unverified
**Input**: Implement Librarr and integrate compatible existing stacks.

## User Scenarios & Testing

### User Story 1 - Independent book acquisition (Priority: P1)

An operator prepares a portable Librarr instance without modifying existing services.

**Independent Test**: Prepare twice in an isolated fixture, render the example,
and verify existing configuration survives and no containers start.

**Acceptance Scenarios**:

1. Given unset credentials, deployment configuration refuses missing required values.
2. Given absent media storage, preparation refuses without creating the media path.
3. Given existing configuration, preparation preserves its bytes on repeat.

### User Story 2 - Compatible acquisition and readers (Priority: P2)

An operator connects available indexers, a torrent client, and selected readers,
while preserving existing libraries and seeding.

**Independent Test**: Render each reader override and verify shared host paths,
read-only consumer mounts, explicit credentials, and supported upstream interfaces.

**Acceptance Scenarios**:

1. Prowlarr is queried by Librarr without a reverse indexer loop.
2. qBittorrent uses a distinct Librarr category and matching download paths.
3. Kavita and Komga can read dedicated Librarr libraries without overlapping existing roots.
4. Audiobookshelf reads Librarr's audiobook subtree in its existing library.
5. Bookshelf and Calibre-Web have documented reviewed import paths; unsupported automatic handoffs are not enabled.

### Edge Cases

Missing remote mounts, unset reader credentials, source outages, changed UI-saved
settings, unavailable images on non-amd64 hosts, duplicate imports and optional
overrides left unselected must remain explicit.

## Requirements

### Functional Requirements

- **FR-001**: Provide all six stack contract surfaces and a pinned release image.
- **FR-002**: Preserve existing secrets and application state; preparation never starts containers.
- **FR-003**: Require authentication and private persistent state; expose no host port.
- **FR-004**: Configure supported acquisition paths and separate Librarr output from managed Calibre and comic libraries.
- **FR-005**: Make reader networking and additional mounts explicit opt-ins.
- **FR-006**: Document Z-Library configuration without inventing a trusted provider address or committing credentials.
- **FR-007**: Retain torrent payloads and disable background automatic acquisition, cleanup and upgrades initially.
- **FR-008**: Regenerate catalog, topology inventory and public application pages.

### Key Entities

Librarr state contains its catalog, settings and source configuration. Media is
separate, shared with readers through read-only mounts. Provider credentials
belong only in private runtime configuration.

## Success Criteria

- **SC-001**: Every public example renders with synthetic configuration.
- **SC-002**: Repeated preparation preserves existing configuration and media.
- **SC-003**: All documented automatic connections match inspected upstream behavior.
- **SC-004**: Required repository checks pass, with unavailable tools reported separately.

## Assumptions

This is repository implementation, not a live deployment request. Optional stacks
remain independently deployable. Provider/account acceptance and real downloads
require a subsequent configured deployment and preservation workflow.
