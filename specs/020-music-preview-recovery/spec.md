# Feature Specification: Music preview and recovery

**Feature Branch**: Current working branch `main`; delivery branch not created.
**Created**: 2026-09-30
**Status**: Implemented and verified in isolated fixtures
**Input**: User request: "implement the suggestions" — broader audio detection, cleanup preview, summary logs, unchanged-release skip, and recovery command.

This contract was recorded during ongoing implementation, after initial code and
focused tests, before documentation and repository verification. It covers only
these new capabilities; earlier fixes are outside this specification.

## User Scenarios & Testing

### User Story 1 - Recover originals safely (Priority: P1)

An operator restores a release after interrupted processing.

**Why this priority**: Original music must remain recoverable.
**Independent Test**: Interrupt publication in an isolated fixture and recover it.

**Acceptance Scenarios**:

1. **Given** an interrupted release with intact saved originals, **when** recovery runs, **then** every original file and archive is restored byte for byte and the operation workspace is removed.
2. **Given** changed outputs or damaged backups, **when** recovery runs, **then** it refuses before changing files and preserves the workspace.
3. **Given** an interrupted recovery, **when** the same action resumes, **then** originals are verified and restored.

### User Story 2 - Preview cleanup (Priority: P2)

An operator inspects proposed removals and moves for an explicit release.

**Why this priority**: Cleanup decisions should be reviewable before changing music.
**Independent Test**: Preview direct and archived fixture releases and compare source bytes and modification times.

**Acceptance Scenarios**:

1. **Given** tracks, sidecars, archives and a cue sheet, **when** preview runs, **then** it reports planned changes while source bytes and modification times stay unchanged.
2. **Given** invalid archive or cue references, **when** preview runs, **then** it fails without publishing files.

### User Story 3 - Retain recognizable audio and report results (Priority: P2)

An operator processes obfuscated tracks and understands the result.

**Why this priority**: More audio formats should survive cleanup and unknown files need visibility.
**Independent Test**: Process tagless MP3, ADTS AAC and AIFF fixtures, inspect summaries, then reprocess an unchanged release.

**Acceptance Scenarios**:

1. **Given** recognizable audio with misleading extensions, **when** processing runs, **then** correct extensions are restored and media bytes are retained.
2. **Given** unknown files, **when** processing runs, **then** they remain and their names are reported.
3. **Given** an unchanged release, **when** processing runs, **then** it reports counts without staging or publishing files.

### Edge Cases

- Isolated sync-like bytes must not establish MP3 or AAC recognition.
- Corrupt, legacy, unsafe, or incomplete recovery records require refusal and manual review.
- Concurrent script instances or changed source files must fail safely.
- Existing multi-disc identity and cue references remain protected.

## Requirements

### Functional Requirements

- **FR-001**: Retain and repair recognizable tagless MP3, ADTS AAC and AIFF audio.
- **FR-002**: Preview the same cleanup decisions as normal processing without publishing or changing source bytes or modification times.
- **FR-003**: Report media, sidecar, repair, cue, archive and unknown-file counts, plus unknown filenames.
- **FR-004**: Skip staging and publication when the release needs no changes.
- **FR-005**: Recover originals only after validating all saved and current files; refuse changed outputs or corrupt backups.
- **FR-006**: Resume interrupted recovery and retain evidence when verification fails.
- **FR-007**: Require explicit paths for preview and recovery, retaining automatic category behavior for ordinary processing.

### Key Entities

- **Release plan**: Proposed retained files, moves, removals and cue updates.
- **Recovery workspace**: Original files and the record needed to restore and verify them.

## Success Criteria

### Measurable Outcomes

- **SC-001**: All three new audio formats are retained with correct extensions and unchanged contents in isolated fixtures.
- **SC-002**: Preview leaves 100% of source bytes and modification times unchanged for direct and archived fixtures.
- **SC-003**: Recovery restores 100% of original fixture files, refuses changed or corrupt files, and resumes after interruption.
- **SC-004**: An unchanged release performs zero staging or publication operations.
- **SC-005**: Summaries accurately report fixture counts and unknown filenames.

## Assumptions

- Operators stop other writers before recovery; the script lock coordinates script instances only.
- Preview has sufficient temporary storage for copied inputs and extraction.
- Legacy workspaces without integrity evidence remain a manual recovery task.
- Implementation and validation use isolated fixtures; live media processing is outside this request.
