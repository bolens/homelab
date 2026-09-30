# Feature Specification: NZB fallback after DDL exhaustion

**Created**: 2026-09-29

**Status**: Accepted for implementation

**Input**: "in mylar3 when all ddl mirrors are exhausted, can we try searching for an nzb as a last effort?"

## User Scenarios & Testing

### User Story 1 - Last-effort search (Priority: P1)

An operator wants a missing comic to get one NZB search after its DDL mirrors fail.

**Why this priority**: Recover an issue without manually restarting failed downloads.

**Independent Test**: Exhaust a single issue's mirrors with an enabled indexer and downloader, then observe one NZB-only search.

**Acceptance Scenarios**:

1. **Given** a failed regular single issue with confirmed mirror exhaustion, **When** the scheduler runs with intake capacity, **Then** it reserves one NZB-only search using existing providers and candidate checks.
2. **Given** a fallback with no accepted match, **When** search completes, **Then** the DDL remains Failed and future cycles and restarts do not repeat the fallback.
3. **Given** accepted or uncertain downloader submission, **When** the scheduler restarts, **Then** ownership stays held and prevents duplicate submission.

### Edge Cases

- Cooling providers, lookup errors, changed layouts and missing terminal receipts do not establish mirror exhaustion.
- Packs, one-offs, imported issues and issues owned by another task remain excluded.
- Missing NZB configuration leaves the failed entry unchanged.
- Intake pressure delays the search. Manual waiting-entry handoffs retain their existing no-result behavior.

## Requirements

### Functional Requirements

- **FR-001**: Automatically attempt NZB fallback for eligible confirmed exhausted single issues, independently of the optional waiting-age handoff setting.
- **FR-002**: Preserve existing provider configuration, validation, ownership checks and pacing.
- **FR-003**: Remember the attempt per release across restarts and prevent a no-result DDL retry loop.
- **FR-004**: Keep accepted and uncertain submissions held for normal completion or review.
- **FR-005**: Preserve exclusions and make fallback and no-result outcomes visible in Activity.

### Key Entities

- Exhausted release: a failed DDL with confirmed mirror exhaustion and tracked issue identity.
- Fallback attempt: a persistent reservation and its search or downloader outcome.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Every eligible fixture schedules exactly one NZB-only fallback across repeated cycles and restart.
- **SC-002**: No-result fixtures schedule zero DDL retries.
- **SC-003**: Ineligible fixtures submit zero fallback searches.

## Assumptions

- Reuse the existing single-issue handoff scope. Pack-to-member fallback is outside this change.
- Operators already configure NZB indexers and NZBGet or SABnzbd.
- This task changes the repository. Live deployment requires its own verified backup workflow.
