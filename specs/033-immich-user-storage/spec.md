# Feature Specification: Immich per-user photo storage

**Feature Branch**: Existing working branch, local deployment requested

**Created**: 2026-10-31

**Status**: Implemented; acceptance evidence in tasks.md

**Input**: Store Immich originals on an existing mounted photo share, under
`immich/<user photos>`, supporting additional users in the future.

## User Scenarios & Testing

### User Story 1 - Store each user's originals separately (Priority: P1)

Users upload through Immich and find their originals beneath their own folder
on the selected photo share. Additional users need no stack reconfiguration.

**Why this priority**: This is the requested storage behavior.

**Independent Test**: Verify the configured destination and an isolated write
through the running application mount, plus account folder selection.

**Acceptance Scenarios**:

1. Given an account with a storage label, finalized originals use that label.
2. Given another account without a label, its unique account ID selects its folder.
3. Given an absent or unconfigured destination, deployment refuses to create it.

### User Story 2 - Preserve existing data and recoverability (Priority: P1)

An operator can migrate storage without losing accounts or files.

**Why this priority**: Changing storage must preserve existing state.

**Independent Test**: Restore the operation's backup in isolation and compare
files, application record counts and database readability.

**Acceptance Scenarios**:

1. Before migration, a consistent backup passes isolated restore verification.
2. After migration, all previous files and records remain available.
3. A failed migration can return to the prior mount and verified state.

### Edge Cases

- A directory exists on the host while the expected remote mount is absent.
- Storage labels are unset or invalid; Immich owns label validation and fallback.
- Uploaded originals remain temporarily in staging until processing completes.
- The destination runs out of space independently of local application storage.

## Requirements

### Functional Requirements

- **FR-001**: Keep the default portable stack usable without a host photo share.
- **FR-002**: Provide explicit optional storage selection that refuses missing paths.
- **FR-003**: Finalized originals MUST use separate user label or unique ID folders.
- **FR-004**: Preserve existing application files, accounts and authentication settings.
- **FR-005**: Keep local application state and database storage unchanged.
- **FR-006**: Verify the expected remote mount before creating destination directories.
- **FR-007**: Document backup coverage, staging behavior and rollback ordering.
- **FR-008**: Validate missing-path refusal and preparation preservation in isolated fixtures.
- **FR-009**: Use capture-date folders and a sortable timestamp-prefixed filename
  that retains the original name and handles collisions, across all accounts.

### Key Entities

- Account: unique identity and optional human-readable storage label.
- Original: uploaded photo/video finalized beneath its owner's folder.
- Storage destination: existing mounted directory owned by the operator.
- Application state: staging, generated files, configuration and database records.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Existing accounts and all baseline files survive the migration.
- **SC-002**: A verified write reaches the selected photo destination.
- **SC-003**: Account folder selection supports both labelled and unlabelled users.
- **SC-004**: Missing-path and missing-setting checks create zero host directories.
- **SC-005**: Service health, signed-in access and required repository checks pass.

## Assumptions

- The operator has authorized live storage configuration and scoped lifecycle changes.
- The existing photo destination is empty, and the library currently has no assets.
- The requested improved template groups by year/month/day and prefixes the
  original filename with capture date and time.
- New accounts are managed through Immich and receive unique storage labels as desired.
- New production accounts are not created solely for testing.
