# Feature Specification: PDF comic normalization

**Feature Branch**: `codex/pdf-comic-normalization`
**Created**: 2026-09-29
**Status**: Planned
**Input**: Convert downloaded PDF art books to usable CBZ files and automate future imports.

## User Scenarios & Testing

### User Story 1 - Read PDF downloads as comics (Priority: P1)
An operator enables PDF conversion and obtains a complete ordered comic from a stable PDF.
**Independent Test**: Convert a mixed landscape/portrait fixture and compare every rendered page with the output archive.
**Acceptance Scenarios**:
1. Given an enabled worker and valid PDF, conversion produces one losslessly encoded image per page, in document order, retaining a verified original.
2. Given a disabled worker setting, PDF files remain untouched.
3. Given encryption, malformed data, excessive resources, or an existing unrelated destination, the source is retained and no incomplete result is published.

### User Story 2 - Import cached books (Priority: P1)
Completed cached PDFs and PDF pack members use existing unique catalog matching and import recovery.
**Independent Test**: A cached PDF with one established issue ID becomes a verified CBZ import without guessing an identity.
**Acceptance Scenarios**:
1. A uniquely matched PDF is converted before import; tagging and reader notifications follow existing policy.
2. Active/partial downloads and ambiguous matches remain unmodified for review.
3. A PDF already indexed by the reader retains reading progress through the existing upgrade process.

### Edge Cases
Rotated pages, mixed page dimensions, unusually large page dimensions, blank pages, Unicode paths, source mutation, corrupt cached derivatives, restart, duplicate destination, missing renderer, and unavailable reader.

## Requirements
- FR-008: Prefer known CBZ/CBR alternatives to PDF among eligible releases without weakening matching or overriding pack/queue ordering.
- FR-001: PDF conversion is opt-in and its output resolution is configurable.
- FR-002: Retain the complete original, its checksum, conversion settings and page inventory outside scanned libraries.
- FR-003: Check every output image and all archive members before publication; preserve page ordering, rotation, and aspect ratio.
- FR-004: Bound pages, output bytes, per-page dimensions, execution time and storage use.
- FR-005: Reuse verified derivatives only when source identity and conversion settings agree.
- FR-006: Integrate existing conversion, matching, tagging, recovery and scan ownership without marking unverified imports complete.
- FR-007: PDF originals retain search text, vectors, links, forms, attachments, color source data and document metadata that raster CBZ cannot preserve.

### Key Entities
Original PDF; rendered page; verified derivative receipt; existing conversion/import receipt.

## Success Criteria
- SC-001: Both available cached books are fully rendered, all page counts match, and representative pages are visually checked before live import.
- SC-002: All failure fixtures retain their originals and publish no incomplete CBZ.
- SC-003: Existing archive conversion fixtures pass unchanged.
- SC-004: Live deployment preserves affected application records and unrelated service uptime, with a verified scoped backup and recovery path.

## Assumptions
CBZ is a reading derivative, not a lossless replacement for a PDF. Default longest page edge is 3200 pixels; spreads remain spreads. No passwords or decryption capability is introduced. Retained partial filenames require separate operational verification and are never automatically promoted.
