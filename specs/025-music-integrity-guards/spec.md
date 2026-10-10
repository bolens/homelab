# Feature Specification: Music integrity guards

**Feature Branch**: `codex/nzbget-music-integrity`
**Created**: 2026-10-08
**Status**: Implemented; repository acceptance verified
**Input**: Implement failed-download guards, cue filename protection guidance,
partial-album checks, optional decoding verification, local playlist completeness
checks, zero-byte audio rejection and recognised binary/text sidecar cleanup.

## User Scenarios & Testing

### User Story 1 - Preserve failed downloads (Priority: P1)

Operators retain damaged or repairable downloads for investigation.

**Why this priority**: Cleanup must not run on downloads already known to have failed.
**Independent Test**: Supply failed and repairable statuses to a fixture release.

**Acceptance Scenarios**:

1. **Given** a failed, warning or deleted download, **when** processing starts, **then** files remain unchanged and processing does not report success.
2. **Given** a successful download or a manual invocation with no reported status, **when** processing starts, **then** normal processing remains available.

### User Story 2 - Detect missing album tracks (Priority: P1)

Operators receive an error for partial tagged albums rather than a successful cleanup.

**Why this priority**: Several remaining tracks can hide earlier loss.
**Independent Test**: Compare partial and complete tagged FLAC fixture albums.

**Acceptance Scenarios**:

1. **Given** tracks 1 and 9 of a ten-track album, **when** processing runs, **then** it refuses before cleanup or publication.
2. **Given** complete albums on separate discs with repeated track numbers, **when** processing runs, **then** it preserves all tracks.
3. **Given** cue-based album images or untagged audio, **when** processing runs, **then** it does not invent missing tracks.

### User Story 3 - Verify audio and protect cues (Priority: P2)

Operators can verify audio decoding and preserve cue filenames through earlier renaming.

**Why this priority**: Filename checks cannot detect damaged audio or restore lost cue references.
**Independent Test**: Enable verification for valid and damaged temporary audio, and verify the documented cue exclusion setting.

**Acceptance Scenarios**:

1. **Given** enabled verification and undecodable audio, **when** processing runs, **then** originals, archives and sidecars remain unchanged.
2. **Given** unavailable verification tools, **when** enabled verification is requested, **then** it reports the missing dependency without changing files.
3. **Given** an existing rename exclusion list, **when** cue protection is added, **then** existing entries and unrelated settings remain intact.

### User Story 4 - Detect incomplete playlist releases (Priority: P1)

Local M3U-style playlists provide completeness evidence when track totals are absent.
Matching numbered artist/title filenames to a single tagged FLAC album supports
obfuscated downloads. Missing entries block cleanup; unrelated or unsafe text stays.
Complete recognised extensionless playlists can be removed during cleanup.

### Edge Cases

- Conflicting totals or duplicate track numbers require an error, not guessed completeness.
- Metadata that cannot be read is not evidence of a complete album.
- Album images with external or embedded cues are exempt from track-file counting.
- Verification must run even when the release needs no filename changes.
- Verification failure, timeout, or missing tools occurs before publication.

## Requirements

### Functional Requirements

- **FR-001**: Preserve files on unsuccessful NZBGet download statuses, including legacy repair/unpack status values.
- **FR-002**: Validate the number and uniqueness of tagged FLAC tracks within separate album/disc groups.
- **FR-003**: Preserve existing cue/image exceptions and retain files with unknown metadata.
- **FR-004**: Offer optional audio decoding verification in normal processing and preview.
- **FR-005**: Enabled verification must fail safely on decoder errors, timeouts and missing tools.
- **FR-007**: Recognise CP437 box-art and black-square NFO sidecars with otherwise printable ASCII without deleting unknown binary or cue-protected files.
- **FR-006**: Document cue exclusions while instructing operators to preserve existing rename exclusions.

- **FR-008**: Recognise bounded UTF-8 local M3U-style playlists, including extensionless files; reject missing tracks when existing files establish the playlist relationship.
- **FR-009**: Preserve ambiguous, remote and unsafe playlist-like text and all files on completeness failure.

- **FR-010**: Reject zero-byte files with known audio extensions before mutation, regardless of track totals, cleanup settings or optional decoder availability.
- **FR-011**: Reject gaps and duplicate numbers in fully numbered FLAC album/disc groups without declared totals; preserve unknown metadata and cue-image exceptions. A contiguous prefix does not establish the final track count.
- **FR-012**: Reconcile nonempty track/disc aliases and slash totals, including repeated numeric keys. Blank values must not hide completeness evidence. Reject contradictory values and declared missing discs before publication.
- **FR-013**: Keep grouping stable across repeated processing when flattening would combine independent editions or numbered FLAC folders lacking album identity.
- **FR-014**: Offer default-off RequireCompleteness and preview support. Refuse otherwise unproven audio even on unchanged/cleanup-disabled paths. Accept validated FLAC totals, complete covering local playlists and cue-image exceptions. Retain and repair strict-mode playlist evidence for retries, preserving sources and archives on failure.
- **FR-015**: Require distinct resolved audio files for recognized playlist entries, reconcile obfuscated playlist position aliases, and limit disc context to the selected release tree. Preserve valid independent editions under disc-named ancestors and across differing disc labels. Merge compatible repeated position/total values. Require rewritten strict playlist references to round-trip through the reader, preserving all source files on ambiguity or unrepresentable-path failure.



### Key Entities

- **Album/disc group**: Tagged track files with shared album identity and disc context.
- **Verification result**: Whether selected audio decodes successfully before publication.
- **Rename exclusion list**: Extensions protected from upstream NZBGet renaming.

## Success Criteria

### Measurable Outcomes

- **SC-001**: All unsuccessful-status fixtures leave 100% of input files unchanged.
- **SC-002**: Partial and duplicate-number fixtures fail; complete separate-disc fixtures retain 100% of track contents.
- **SC-003**: Valid audio passes optional verification; corrupted audio fails with originals and archives unchanged.
- **SC-004**: Cue protection guidance preserves existing exclusions and explains the earlier-renaming risk.

## Assumptions

- Runtime audio verification is opt-in and requires an installed decoder.
- FLAC totals describe tracks on a disc; malformed, ambiguous or intentionally partial metadata may require manual correction.
- Unknown formats and absent totals cannot establish completeness.
- The script cannot restore previously overwritten audio; recovery and service operations remain separate from repository acceptance.
