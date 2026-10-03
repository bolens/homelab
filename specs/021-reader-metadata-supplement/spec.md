# Feature Specification: Reader metadata supplements

**Feature Branch**: `codex/reader-metadata-supplement`
**Created**: 2026-10-02
**Status**: Implementation in progress
**Input**: Add reader-supported fields and run repeatable supplementation of missing library tags.

## User Scenarios & Testing

### User Story 1 - Discover comics by metadata (Priority: P1)
Readers can browse comics using character, team and location labels and publisher collections.
**Independent Test**: A comic with existing credits gains searchable labels and a publisher collection.
**Acceptance Scenarios**:
1. Given established credits, supplementation exposes those facts without changing their source fields.
2. Given existing custom labels and collections, supplementation retains them.

### User Story 2 - Fill verified missing fields (Priority: P2)
An operator can supply verified genres, language, ratings, reading direction, ISBNs and ordered arcs for a scoped library.
**Independent Test**: Verified values fill blank fields; conflicting existing values remain intact.
**Acceptance Scenarios**:
1. Given an existing arc, a new order does not attach to that arc implicitly.
2. Given invalid ISBNs, ratings or arc pairs, the operation rejects the policy before changing files.

### User Story 3 - Repeat safely (Priority: P1)
An operator can preview, apply and repeat library supplementation.
**Independent Test**: Applying twice leaves identical bytes on the second pass.
**Acceptance Scenarios**:
1. Given an eligible archive, a restored backup is checked before publication.
2. Given a failure, the operation stops and retains recovery evidence.

### Edge Cases
- Missing, duplicate or nested metadata requires separate repair and is reported.
- Concurrent writers cannot publish during a supplementation operation.
- Existing custom metadata, bookmarks, pages and sidecars survive.
- Missing factual sources leave fields absent rather than assigning guesses.

## Requirements

### Functional Requirements
- **FR-001**: Preserve existing scalar fields, custom collections and unknown metadata.
- **FR-002**: Extend existing labels with deduplicated character, team and location labels.
- **FR-003**: Fill missing collections from the established publisher.
- **FR-004**: Accept validated explicit overrides for Genre, LanguageISO, AgeRating, Manga, GTIN, SeriesGroup, StoryArc/StoryArcNumber and Tags.
- **FR-005**: Default to a read-only preview; require explicit apply and private backup storage for writes.
- **FR-006**: Verify isolated restoration and preserve archive members, permissions and extended attributes before declaring completion.
- **FR-007**: Coordinate with existing writers and retain durable publication recovery on failure.
- **FR-008**: Add derived reader fields to future Modern tagging, respecting no-overwrite behavior.

### Key Entities
- Supplement policy: verified optional missing-field values scoped by the operator.
- Archive metadata: existing facts and operator labels.
- Publication receipt: durable recovery and verification evidence.

## Success Criteria

### Measurable Outcomes
- Every eligible archive either receives its missing derived fields or has an explicit failure result.
- Every second pass reports no further derived additions and changes no archive bytes.
- Every modified archive retains identical decoded non-metadata contents.
- Komga exposes the added labels and collections after metadata refresh.

## Assumptions
- Existing publisher and credit metadata are the factual source for automatic additions.
- Other fields require verified explicit values; filenames alone do not establish language, maturity, genre or reading order.
- The current supported roots contain CBZs with root ComicInfo metadata; PDFs retain their native format.
- Existing service and network contracts suffice; no new mount, port, dependency or credential is introduced.
