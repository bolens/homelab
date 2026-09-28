# Feature Specification: Verified pack tracking and recovery

**Feature Branch**: `codex/mylar-pack-tracking`

**Created**: 2026-09-28

**Status**: Accepted for implementation

**Input**: Automate recently recovered import failures and track annuals, alternate covers, and other related pack contents.

## User Scenarios & Testing

### User Story 1 - Imports finish without manual repair (Priority: P1)

An operator downloads comics and expects readable annuals and regular issues to import without blocking the queue.

**Independent Test**: Submit an identified annual followed by an empty directory and a valid issue.

**Acceptance Scenarios**:

1. Given an annual identified by its catalog issue ID, processing imports it under its parent series with correct annual identity.
2. Given unreadable, empty, or failing input, processing releases only its own lock and later work continues.
3. Given a pack linked to a different edition or series, no unrelated issue becomes downloaded or snatched because of that link.

### User Story 2 - All related pack contents are accounted for (Priority: P1)

An operator keeps full issues, annuals, variant covers, and worthwhile extras without confusing their identities.

**Independent Test**: Process a pack containing an issue, annual, cover collection, alternate scan, duplicate, and ambiguous edition twice.

**Acceptance Scenarios**:

1. Missing catalog entries are added automatically only when exact catalog evidence confirms their identity and relationship; uncertain candidates remain for review.
2. Covers and supplements are retained separately and never satisfy a full issue's wanted status.
3. Confirmed duplicates are cleaned only after page and sidecar preservation checks. Repeated runs neither duplicate supplements nor resubmit uncertain imports.
4. Pack history retains each member's classification, import state, and verification outcome across restarts and DDL history cleanup.

### User Story 3 - Status describes actual outstanding work (Priority: P2)

An operator sees pack members and remaining problems in the existing authenticated interface.

**Independent Test**: Inspect partially imported and fully verified packs after queue completion and restart.

**Acceptance Scenarios**:

1. Downloaded is distinct from queued, processing, imported, preserved extra, and needs review.
2. Pack completion requires every inventoried member to be accounted for; an imported anchor issue alone is insufficient.
3. A replaced corrupt download is shown as resolved without losing its quarantine history or triggering another replacement search.

### Edge Cases

- Mixed editions, conflicting tags, duplicate issue numbers, deleted annuals, short legitimate comics, missing catalog connectivity.
- Nested packs, unsafe paths, links, oversized extraction, changing files, active downloads, interrupted conversion or import acknowledgement.
- Destination collisions, missing library files, old receipts, worker or application restart, preservation verification failures.

## Requirements

### Functional Requirements

- **FR-001**: Release processing ownership on every exit without clearing another run's ownership.
- **FR-002**: Resolve annual identities and include them in recovery and confirmation.
- **FR-003**: Inventory pack contents with durable source identity and per-member outcomes.
- **FR-004**: Automatically catalog exact, related missing entries; ambiguity must preserve the source and require review.
- **FR-005**: Preserve related supplements independently from regular issues, including original images and non-metadata sidecars.
- **FR-006**: Never infer edition from issue number and similar title alone or mark unverified whole-pack members snatched.
- **FR-007**: Retain sources until content preservation is established; bound extraction, conversion and retries.
- **FR-008**: Expose pack progress and supplements through existing authenticated navigation with readable buttons at all screen sizes.
- **FR-009**: Keep failure and resolved quarantine history without endless automatic retries.
- **FR-010**: Publish reproducible images and verify backed-up live state after a scoped deployment; roll back missing or corrupt data.

### Key Entities

- **Pack**: Download identity, source version, inventory completeness, members, aggregate outcome.
- **Member**: Original name/format, content identity, related series, catalog identity when known, classification, destination and verification.
- **Supplement**: Preserved related cover, alternate scan or extra that does not replace a catalog issue.
- **Import receipt**: Attempt ownership and confirmed outcome, distinct from submission acceptance.

## Success Criteria

### Measurable Outcomes

- **SC-001**: All representative annual and processing-exit regressions complete without a stranded processing lock.
- **SC-002**: Every member of the representative mixed pack has a truthful durable outcome, including after a second pass and restart.
- **SC-003**: No cover-only fixture or wrong-edition fixture satisfies a regular issue or causes an unrelated status change.
- **SC-004**: All verified imports preserve page bytes and non-metadata sidecars; no unverified source is deleted.
- **SC-005**: Deployment retains baseline data, confirmed files, unrelated settings and uninterrupted NZBGet/Komga uptime.

## Assumptions

- Existing Mylar authentication, catalog credentials and optional maintenance worker are reused.
- The normalizer owns archive conversion; Mylar owns catalog issue tagging and issue status.
- Public examples retain opt-in automatic recovery. This user's live recovery is authorized.
- Catalog ambiguity and unsupported content remain visible, rather than being forced into a likely series.

## Added queue scheduling scope

The user also requested queue management preferences during implementation. The
DDL page must persist oldest-first, newest-first, singles-first, packs-first and alternating preferences,
plus pause-new-starts and one-item download-next controls. Changes affect the next
eligible transfer, preserve provider cooldowns and active downloads, and do not
confuse visual table order with actual scheduling. This scope was added during
implementation; its acceptance evidence belongs with the final candidate.

The queue table must also offer **Download queue order**, using the same saved
preference and one-item priority as the scheduler. Eligible queued downloads
precede provider cooldowns, active downloads stay first, and history follows
queued work. The display is an estimate that refreshes as eligibility changes.
It remains usable while downloads are paused. Download settings and display
sorting must be separately labeled and usable at narrow and wide widths.
