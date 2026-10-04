# Feature Specification: Verified comic release naming

**Feature Branch**: `codex/comic-release-naming`
**Created**: 2026-10-03
**Status**: Naming delivered; bulk and pack-evidence correction in progress
**Input**: Add release naming to comic normalization, then perform a bulk library pass. Use dots as separators and a hyphen before the release group. Preserve edition distinctions and additional verified identity information.

## User Scenarios & Testing

### User Story 1 — Consistent normalized release names (Priority: P1)

An operator receives a normalized comic whose name identifies its series, issue or collected volume, publication year, source and group. Annuals, specials, separate series volumes and collected editions remain distinct.

**Independent Test**: Normalize verified fixtures and compare output names, archive payloads, Mylar ownership and reader results.

**Acceptance Scenarios**:

1. **Given** a uniquely cataloged comic with matching embedded identity, **when** naming is enabled, **then** the output uses dots between fields and a hyphen before the known release group.
2. **Given** an annual, variant, reprint, cover-only supplement or Deluxe collection, **when** a name is proposed, **then** its proven distinctions remain visible and it cannot fulfill a different regular issue.
3. **Given** ambiguous ownership, contradictory metadata, an unknown publication year or a destination collision, **when** naming runs, **then** the source is retained for review without a guessed identity or overwrite.

### User Story 2 — Recoverable library renaming (Priority: P1)

An operator renames already normalized files without losing content, catalog locations or reader progress.

**Independent Test**: Interrupt each publication/catalog/reader boundary and retry; prove the original or verified destination remains recoverable, exactly one catalog path is authoritative and reader progress survives.

**Acceptance Scenarios**:

1. **Given** a verified existing CBZ, **when** it is renamed, **then** all archive bytes, sidecars and release credits survive and Mylar references its new location.
2. **Given** an uncertain reader response or process interruption, **when** the worker retries, **then** it reconciles its durable receipt before attempting another mutation.
3. **Given** another native writer or unfinished conversion, **when** renaming is due, **then** shared coordination prevents overlapping writes.
4. **Given** confirmed DDL pack members, **when** a verified rename or metadata publication changes their paths or file signatures, **then** every matching pack retains confirmation through a durable exact-owner/hash transition while unrelated, changed and unconfirmed members remain untouched.

### User Story 3 — Auditable bulk pass (Priority: P2)

An operator applies the same naming policy to eligible existing library entries using a reviewed old-to-new manifest and bounded batches.

**Independent Test**: Create a dry-run manifest, change a source or catalog after planning, then apply it; unchanged verified entries complete, stale entries remain for review and a second pass proposes no duplicate work.

### Edge Cases

Titles containing years, Unicode, punctuation and fractions; annual release versus parent IDs; numeric variants; collected volume numbers; scanner groups with internal hyphens; absent group/source labels; equivalent case-insensitive destinations; linked paths; NFS interruptions; sidecar naming; existing conversion receipts; metadata supplements without catalog ownership; reader progress for multiple users; resumed native intake.

## Requirements

### Functional Requirements

- **FR-001**: Naming MUST be explicitly enabled and portable examples MUST default to disabled.
- **FR-002**: Naming MUST use dotted release fields with `-Group` at the end, for example `Series.Name.v2.Annual.001.(2020).(Digital)-Group.cbz`.
- **FR-003**: Names MUST retain verified series volume, publication year, annual/special/collection labels, editions, variants, reprints, cover-only status, source and existing release credits. Unknown fields MUST NOT be guessed. A regular catalog issue without a filename year may use matching embedded Year and stored issue date only when the exact canonical ComicVine issue link is present; explicit date contradictions remain for review.
- **FR-004**: Catalog IDs and tagging history MUST remain in ComicInfo and private recovery records; transient verified import markers MUST NOT become release-group text.
- **FR-005**: Only unique existing ownership with consistent embedded identity may be renamed automatically. Supplements and uncataloged collections require explicit proven publication identity or remain for review.
- **FR-006**: Planning MUST reject symlinks, unsafe paths, oversize metadata, contradictory IDs and case-insensitive collisions.
- **FR-007**: Publication MUST preserve archive bytes and filesystem attributes; sidecars MUST remain attached or the operation MUST stop for review.
- **FR-008**: All mutations MUST use existing writer coordination and durable receipts. Uncertain API acknowledgements MUST be reconciled rather than automatically replayed.
- **FR-009**: Mylar location/status ownership and reader readiness/progress MUST be verified before completion. Originals and backups MUST be retained until that proof succeeds.
- **FR-010**: Bulk operation MUST support a read-only manifest, bounded application, source/catalog freshness checks, resumable outcomes and an idempotent second pass.
- **FR-011**: New behavior MUST preserve disabled-policy compatibility and existing conversion, tagging, annual and pack recovery contracts.
- **FR-012**: A combined bulk rename/metadata pass MUST handle each publication under one retained preservation set. It MUST prove the unchanged-hash reader move before changing ComicInfo, then prove final payloads, catalog ownership and reader readiness before removing that set. Metadata additions MUST exclude files with unverified credits; the combined receipt MUST retain separate before-rename and after-tag hashes.

- **FR-013**: Controlled rename and metadata publication MUST retain truthful DDL pack confirmation. Capture exact prior owner, path, hash and file identity before publication, then bind every matching confirmed member to the verified final path/hash/signature before clearing recovery fences. Reconciliation MUST be idempotent and atomic across matching pack records, preserve inventories, sidecars and cleanup history, reject foreign ownership/content, and never promote unconfirmed members.

### Key Entities

- **Release identity**: Catalog owner, issue/annual/collection number, series/publication years and distinguishing edition metadata.
- **Naming proposal**: Old/new paths, source identity/hash, ownership and retained labels.
- **Rename receipt**: Durable publication, catalog and reader stages with preservation and recovery evidence.
- **Bulk manifest**: Verified proposals and reasons for skipped/review entries.

## Success Criteria

- Every accepted rename uses the requested release convention and preserves exact archive bytes.
- No ambiguous identity or collision changes a file or catalog assignment.
- Retry tests at every state boundary preserve recoverability and produce one completed result.
- Mylar points to each completed destination and Komga reads the same verified pages with preserved user progress.
- A second completed bulk pass proposes no further changes for its accepted files.

## Assumptions

Folders remain unchanged. Existing scanner/source labels are preserved rather than invented. Publication year belongs to the issue; series start year/volume distinguishes runs. Renaming is not evidence that incorrect metadata has been repaired. The live pass follows restore-verified backups and coordination with other media writers.
