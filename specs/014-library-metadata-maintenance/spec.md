# Feature Specification: Automatic library metadata maintenance

**Feature Branch**: `codex/library-metadata-maintenance`
**Created**: 2026-09-29
**Status**: Planned
**Input**: Automatically handle duplicate nested metadata and untagged library comics.

## User Scenarios & Testing

### User Story 1 - Fill missing library tags (Priority: P1)

An operator enables library maintenance and downloaded catalog comics without tags enter the existing tagging queue, without repeating completed work.

**Independent Test**: An exact downloaded issue without tags is queued once. A tagged extra and ambiguous file remain unchanged.

**Acceptance Scenarios**:
1. Given an untagged catalog comic, when an idle sweep reaches it, then one durable tagging job appears and completes with the correct issue metadata.
2. Given existing tags or a supplement, when maintenance runs, then existing tags and files remain unchanged.
3. Given active imports, when maintenance is due, then imports retain priority.

### User Story 2 - Reconcile nested duplicates (Priority: P1)

A second opt-in repairs one nested copy agreeing with the root issue identity. Root values win. Missing safe fields are merged and original nested XML remains as provenance.

**Independent Test**: Repair a root plus agreeing nested copy, compare every page and extra, and interrupt publication at each boundary.

**Acceptance Scenarios**:
1. Given agreeing duplicate tags, when repair completes, then only root ComicInfo is active and the nested original bytes remain available under a provenance name.
2. Given conflicting identities, malformed XML, unsupported archives or a provenance-name collision, then the file stays unchanged and a review reason appears.
3. Given interrupted publication, when Mylar restarts, then existing recovery verifies or restores the file before another writer proceeds.

### User Story 3 - Control and inspect maintenance (Priority: P2)

Operators can enable either capability separately and see durable outcomes in the existing authenticated interface.

**Independent Test**: Settings persist, disabled options admit no work, and review outcomes remain visible after restart.

### Edge Cases

Changed files, symlinks, hardlinks, corrupt archives, duplicate catalog owners, deleted annuals, non-CBZ files, root-only metadata, nested-only metadata, incomplete supplemental tags, missing mounts, interrupted repairs, queued conversions and disabled Modern tagging fail closed or defer without overwriting content.

## Requirements

### Functional Requirements

- **FR-001**: Both settings default off and are independently configurable through existing authenticated settings.
- **FR-002**: Scan only uniquely owned downloaded catalog CBZs, incrementally while native imports are idle. Unchanged inspected files do not need repeated full reads.
- **FR-003**: Missing ComicInfo is automatically admitted to the existing durable queue with its current source fingerprint. Existing alternate metadata is preserved for review.
- **FR-004**: Repair only exactly one root and one nested copy whose issue identities agree. Keep authoritative root values, merge missing safe fields, preserve conflicting source data as provenance, and preserve all pages, extras and supported file attributes.
- **FR-005**: Use shared writer coordination, verified source staging and durable publication recovery. Changed sources and uncertain outcomes retain copies and require review.
- **FR-006**: Show progress, completed work and review reasons without exposing credentials. Repeated scans and queue replays cannot repeat publication for unchanged files.
- **FR-007**: Existing conversion tagging and native import behavior remain compatible. No new ports, mounts, credentials or service restarts for dependent services.

### Key Entities

- Library observation: catalog path, source version, inspection result, next scan cursor.
- Metadata job: exact source fingerprint, catalog ownership, attempt/recovery identity and durable outcome.
- Maintenance policy: missing-tag discovery and nested-copy repair choices.

## Success Criteria

- **SC-001**: All eligible fixtures are admitted once and tagged with their catalog issue identity.
- **SC-002**: Every repaired archive retains identical page/extra bytes and supported attributes, with one active metadata entry.
- **SC-003**: Conflicting, unsupported and changed fixtures remain untouched and produce an actionable review result.
- **SC-004**: Interrupted operations recover without losing source data or duplicating work.
- **SC-005**: Disabled settings admit no new work. Disabling discovery leaves already admitted tagging jobs intact; disabling nested repair defers pending repair jobs. A full sweep reaches every stable eligible catalog entry and does not block active imports.

## Assumptions

- Modern ComicRack tagging and the existing coordinated writer protocol are prerequisites for mutation.
- Annuals use their release catalog identity. Supplements without an exact downloaded issue are outside automatic mutation scope.
- Existing settings and ingress authentication are reused. Initial rollout enables the requested options only after verified backup and acceptance checks.
- No real power-loss test or full-library backup is required. Preserve only canary/affected files and application state.
