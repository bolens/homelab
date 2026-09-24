# Feature Specification: Automatic comic archive normalization

**Created**: 2026-09-23

**Status**: Accepted for implementation

**Input**: Automatically convert CB7, CBT, and other supported comic archives to CBZ, like the existing CBR workflow.

## User Scenarios & Testing

### User Story 1 - Read newly added archive formats (Priority: P1)

New comic archives become readable CBZ files without a manual conversion step.

**Independent Test**: Add valid CB7 and CBT fixtures, wait for the configured
settling period, and verify matching CBZ pages and automatic library analysis.

**Acceptance Scenarios**:

1. Given a stable supported archive, conversion preserves all member names,
   page bytes, ordering by filename, and sidecars before publishing a CBZ.
2. Given a file still being copied, conversion waits until it is stable.
3. Given a mislabeled non-ZIP CBZ, the actual archive format selects conversion.

### User Story 2 - Preserve existing library records (Priority: P1)

Conversion preserves existing books, reading progress, and Mylar tracking.

**Independent Test**: Upgrade an indexed comic and verify its metadata and
reading progress remain, then verify Mylar finds the new CBZ path.

**Acceptance Scenarios**:

1. An indexed book retains metadata, reading progress, and read-list membership when its archive format changes.
2. Successful conversion triggers analysis and a recheck of the affected Mylar series.
3. Original archives remain recoverable outside the scanned library.

### User Story 3 - Recover from failures (Priority: P1)

Failures do not destroy originals or publish incomplete comics.

**Independent Test**: Exercise corrupt archives, destination collisions,
interrupted work, and unavailable library services.

**Acceptance Scenarios**:

1. Damaged, encrypted, unsafe, or unsupported archives remain intact with an error report.
2. A conflicting destination is never overwritten.
3. Restarting the worker resumes verified pending work without duplicate books.
4. Missing library mounts prevent work without creating replacement media directories.

### Edge Cases

- Archive signatures disagree with extensions.
- No page images, duplicate member names, traversal paths, or symlinks.
- Sources change during conversion or a destination appears concurrently.
- API requests time out after the server has accepted work.
- Multiple libraries contain the same relative filename.

## Requirements

### Functional Requirements

- **FR-001**: Support ZIP/CBZ, RAR/CBR, 7z/CB7, TAR/CBT, and gzip, bzip2,
  xz, and Zstandard compressed TAR archives.
- **FR-002**: Use validated archive conversion and compare all member hashes,
  names, and page inventories before publication. Do not transcode images.
- **FR-003**: Process only regular stable files beneath explicitly configured roots.
- **FR-004**: Preserve source archives outside library roots with recovery receipts.
- **FR-005**: Preserve indexed book metadata, progress, and read-list membership; record replacement IDs and refresh affected library records.
- **FR-006**: Run automatically with bounded concurrency, persistent retry state,
  and observable health and errors.
- **FR-007**: Keep credentials outside tracked examples and logs. Expose no new port
  or Docker socket and run conversion without root privileges.
- **FR-008**: Verify backups and original data before live deployment; retain recovery
  state until service behavior and data preservation are proven.

### Key Entities

- Candidate: library root, relative filename, stable file identity, detected format.
- Conversion receipt: source digest, verified CBZ digest and member inventory,
  original archive location, reader book identity, and pending refresh state.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Every supported fixture produces a CBZ with identical archive-member contents.
- **SC-002**: No rejected fixture loses its source or overwrites a destination.
- **SC-003**: Repeated runs and interrupted-run recovery produce one reader book per comic.
- **SC-004**: Existing book metadata, reading progress, and read-list membership survive successful conversion.
- **SC-005**: New stable archives begin processing within two configured polling intervals.

## Assumptions

- PDF and EPUB remain native reader formats; rasterization is outside archive repackaging.
- ACE, encrypted archives, and multipart archives are not promised decoder support.
- Source container timestamps and compression metadata may change; page files and sidecars do not.
- Operators provide existing mounted media roots and separate writable recovery storage.
