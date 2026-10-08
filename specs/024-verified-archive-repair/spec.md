# Feature Specification: Verified archive repair

**Feature Branch**: `codex/comic-worker-decoder`

**Created**: 2026-10-08

**Status**: Prospective implementation

**Input**: User request: identify malformed comic archives that can be repaired automatically without losing content, and implement those repairs with a separate subagent while completing library recovery.

## User Scenarios & Testing

### User Story 1 — Explain an archive refusal (Priority: P1)

An operator sees whether a refused comic has a supported lossless repair, requires a compatible decoder or conversion, or needs retained review.

**Why this priority**: A decoder error must not be mistaken for missing or corrupt comic content.

**Independent Test**: Inspect ordinary valid comics and refused fixtures; valid comics retain ordinary processing, while every refused fixture remains retained with a truthful bounded reason.

**Acceptance Scenarios**:

1. **Given** a valid comic archive, **When** ordinary verification succeeds, **Then** repair classification is unnecessary and processing follows existing ownership checks.
2. **Given** an archive containing one empty directory whose name is missing its trailing slash, **When** all content is readable and complete, **Then** diagnostics identify a supported repair candidate without claiming import or publication.
3. **Given** unreadable content, unsafe names, ambiguous members or changed evidence, **When** classification runs, **Then** the source remains retained and no repair completion is claimed.
4. **Given** a decoder-specific refusal or a document requiring conversion, **When** diagnostics run, **Then** they distinguish compatibility or conversion from proved corruption.

### User Story 2 — Prepare a lossless repaired copy (Priority: P1)

An operator can prepare a supported repaired copy while keeping the original and its publication identity intact.

**Why this priority**: A readable replacement is useful only when every original member, page and metadata payload survives.

**Independent Test**: Prepare a supported fixture, independently read the result, and compare complete content and source evidence; preparation changes no library or catalog state.

**Acceptance Scenarios**:

1. **Given** a freshly verified supported defect and exact publication owner, **When** preparation succeeds, **Then** the separate repaired copy preserves all members, ordered pages, metadata and compressed content, and the original is unchanged.
2. **Given** a changed source, owner, retained copy or repair plan, **When** preparation is checked again, **Then** it is held without refreshing the old proof into permission.
3. **Given** preparation stops or loses its response, **When** processing resumes, **Then** the preserved original and private evidence remain available and no automatic publication replay occurs.

### User Story 3 — Publish a verified repair through normal recovery (Priority: P2)

The automation can adopt a supported repaired copy through its existing coordinated recovery flow after proving current native ownership, correction policy and reader continuity.

**Why this priority**: A repair must unblock processing without introducing duplicate publications or damaging reader references.

**Independent Test**: Complete one isolated owned repair and refusal/crash cases, then verify the live retained example under a consistent verified backup; unrelated comics and reader records stay unchanged.

**Acceptance Scenarios**:

1. **Given** a current owned repaired copy with preserved custody and verified reader continuity, **When** adoption completes, **Then** the exact repaired bytes are usable under the correct publication and only the owning recovery records acknowledge completion.
2. **Given** a rejected or ambiguous publication owner, **When** repair is attempted, **Then** the existing correction hold remains effective despite unchanged comic content.
3. **Given** publication or reader verification is inconclusive, **When** recovery stops, **Then** original custody remains preserved and the affected work remains held.

### Edge Cases

- CRC failure, truncated data, missing content, encryption and unsupported verification never justify inventing, skipping or discarding comic members.
- Duplicate names, case or metadata aliases, links, nonempty directories and contradictory type flags remain uncertain.
- Source replacement, hardlinks, ancestor changes, concurrent catalog or reader changes, and changed private evidence invalidate preparation.
- Ordinary verification remains authoritative for valid ZIP variants outside the initial repair format.
- Unknown responses, partial state, restart and interrupted cleanup preserve custody rather than repeat publication.
- A private repaired copy, successful test or healthy container does not establish live import or whole-library acceptance.

## Requirements

### Functional Requirements

- **FR-001**: Preserve ordinary verification and publication policy; repair diagnostics cannot waive an ordinary refusal.
- **FR-002**: Initially support only the exact lossless correction of one empty directory missing its trailing slash when every member can be completely verified.
- **FR-003**: Bound classification and preparation by source size, expanded content, member count and time; unsupported inputs remain retained.
- **FR-004**: Verify every original and resulting member, page order, metadata payload, compressed content and undeclared archive bytes before accepting a repair.
- **FR-005**: Retain the original and its current file identity; write repaired bytes only to a separate exclusive private preparation location before adoption.
- **FR-006**: Bind preparation to fresh source, owner, complete correction state, current catalog and verified custody; stale or incomplete evidence remains held.
- **FR-007**: Preserve correction holds for rejected and ambiguous owners even when original and repaired comic content is identical.
- **FR-008**: Require a dedicated owning repair operation; existing metadata correction and ordinary import routes must not infer repair permission.
- **FR-009**: Before adoption, independently verify the repaired copy and preserve the exact affected reader references, page continuity and unrelated records.
- **FR-010**: Use a consistent verified backup and independently restored affected application state before live adoption; retain custody through inconclusive verification.
- **FR-011**: Record preparation, dispatch uncertainty, acceptance or rollback durably; uncertain operations cannot be automatically retried as new publication.
- **FR-012**: Distinguish a diagnostic candidate, prepared copy, accepted publication and completed import in user-visible evidence.
- **FR-013**: Keep decoder compatibility and document conversion separate from archive structural repair; do not classify an error message alone as corruption proof.
- **FR-014**: Keep diagnostic output free of private paths, archive content and credentials, and preserve existing release filename preferences during later normalization.
- **FR-015**: Verify matching application and worker behavior before rollout and keep unfinished writer holds until their owning library acceptance succeeds.

### Key Entities

- **Repair diagnosis**: Bounded classification of an unchanged source, supported defect or retained refusal, with no publication permission.
- **Repair preparation**: Exact source, repaired copy, complete preservation evidence, current owner and private custody binding.
- **Repair publication**: An owned transition that joins accepted preparation, current correction policy, native catalog and reader continuity.
- **Repair recovery record**: Durable phase, accepted or uncertain outcome, retained custody and evidence needed to verify completion or rollback.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Every accepted supported repair preserves 100% of member content, ordered pages and metadata; original content remains recoverable.
- **SC-002**: Every damaged, unsafe, stale, ambiguous or rejected-owner test case remains held, with zero lost originals or false import acknowledgements.
- **SC-003**: All interruption and lost-response cases preserve evidence and prevent unverified repeated publication.
- **SC-004**: Scoped live acceptance verifies the repaired comic, its correct publication and affected reader references, with zero unrelated catalog or reader changes.
- **SC-005**: Valid comics keep their ordinary processing path without unnecessary repair work.

## Assumptions

- Initial scope is one verified empty-directory spelling defect; additional repair families require separate preservation proof and contract review.
- Existing ownership, shared writer, backup, publication correction, import and reader coordination remain authoritative.
- A broad reading-progress audit remains deferred; exact affected references and page continuity still require preservation.
- Earlier private diagnostic experiments are preliminary evidence, not retrospective production implementation or feature completion.
