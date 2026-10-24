# Feature Specification: Librarr supplements Bookshelf through Flood

**Created**: 2026-10-23
**Status**: Accepted for implementation
**Input**: Supplement missing Bookshelf ebooks using Librarr and send torrents to Flood on the existing media mount.

## User Scenarios & Testing

### Missing ebooks (Priority: P1)
An operator searches missing monitored ebooks through Librarr, selects matching ebook editions, and imports completed files through Bookshelf while retaining the download.

**Independent Test**: A known matching ebook is queued once and its completed copy is recognized in Bookshelf. Uncertain matches are skipped with a reason.

### Torrent visibility and storage (Priority: P1)
Librarr-submitted torrents appear in the existing Flood instance and use dedicated ebook, audiobook, and manga directories beneath downloads/librarr on the configured mounted media root.

**Independent Test**: An authorized small torrent reaches its dedicated directory and appears in Flood without changing existing torrent paths.

### Edge Cases
Unavailable sources, credentials, absent mounts, ambiguous editions, duplicate queued books, unsafe paths, unrelated torrents, and partial downloads must fail without modifying existing media.

## Requirements

- FR-001: Search only monitored missing ebooks and recheck ownership and existing queues before each submission.
- FR-002: Prefer readable EPUB editions and skip ambiguous title/author matches, audio, comic, and unsupported formats.
- FR-003: Send Librarr torrent acquisitions to the existing rTorrent daemon visible in Flood.
- FR-004: Scope adapter visibility and submission to dedicated paths and Librarr categories. Reject deletion and unsupported commands.
- FR-005: Preserve existing Flood users, sessions, torrents, paths, Bookshelf catalogs, and Librarr authentication.
- FR-006: Generate private integration credentials and publish no adapter port or ingress route.
- FR-007: Verify an isolated backup before configuration or state changes and verify database integrity and existing records afterward.
- FR-008: Completed ebooks enter Bookshelf through its import interface using copy mode. Seeding payloads remain intact.

## Key Entities

Missing book: Bookshelf ID, title, author, desired format.
Candidate: source, title, author, format, torrent hash or direct URL.
Acquisition receipt: book ID, selected candidate, queue identity, status, and eventual imported file.

## Success Criteria

- A second run queues no duplicate acquisitions.
- Every submitted torrent has a dedicated configured path and appears in Flood.
- Existing torrent paths and library records are preserved.
- Completed matching ebooks are registered in Bookshelf; pending transfers and unavailable matches are reported accurately.

## Assumptions

The existing mounted media root is authoritative. Provider credentials are operator supplied. Searches run in bounded batches and skip uncertain candidates. Torrent deletion remains disabled.
