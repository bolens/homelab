# Feature Specification: Paperless user collections

**Created**: 2026-11-04

**Status**: Implemented; prechange file-backup evidence exception recorded in tasks.md

**Input**: Split Paperless document collections per user and store originals in an owner directory on a chosen host filesystem.

## User Scenarios & Testing

### User Story 1 - Private collections (Priority: P1)

Each ordinary user can upload and retrieve their own documents while other ordinary users cannot list, read or download them.

**Independent Test**: Exercise document access as two ordinary accounts, including cross-owner denials. Administrators retain access.

### User Story 2 - Owner directories (Priority: P2)

Original files are stored beneath the configured root in an owner-specific directory.

**Independent Test**: Confirm a document for each account resolves to its owner directory and remains downloadable.

### Edge Cases

- Unmatched shared-inbox imports belong to the administrator.
- Email rules and API callers need explicit ownership review.
- Missing mounts must refuse deployment without creating a substitute directory.
- Unsafe or colliding usernames require operator correction before setup.
- Existing documents need deliberate ownership and verified preservation.

## Requirements

- **FR-001**: Ordinary accounts must have private collections by default.
- **FR-002**: Original files must use owner-specific directories on the selected filesystem.
- **FR-003**: Existing accounts, unrelated settings and persistent data must survive the change.
- **FR-004**: A verified backup must precede live configuration changes.
- **FR-005**: Shared imports must have a known owner rather than becoming visible to all users.
- **FR-006**: The public stack must remain portable and keep host-specific paths and credentials private.

### Key Entities

- Account: collection owner, with separate administrator privileges.
- Document: owned record with original file and optional OCR archive.
- Import route: maps an incoming file to its intended account.

## Success Criteria

- Both ordinary accounts can retrieve their own test document and cannot retrieve the other account's document.
- Every tested original resolves beneath the selected root and the correct owner directory.
- Account and document baseline comparisons match, excluding explicitly created import workflows.
- Backup restore integrity and database readability pass before activation.

## Assumptions

- One Paperless instance and its existing accounts remain in use.
- Only originals move to the selected filesystem. OCR copies, thumbnails and database state retain their current storage.
- Existing sharing is preserved only when explicitly intended. Superusers retain all-document access.
