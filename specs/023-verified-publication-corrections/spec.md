# Feature Specification: Verified publication corrections

**Feature Branch**: `codex/verified-publication-corrections`

**Created**: 2026-10-04

**Status**: Prospective specification; implementation and operational acceptance pending

**Input**: User request: “verify all other comics now and fix the issues that caused things to get out of whack.” Privileged access is available under the scoped backup, independent restore and coordinated rollout requirements.

## User Scenarios & Testing

### User Story 1 — Remember a verified publication correction (Priority: P1)

An operator who has verified that an archive belongs to a different publication records that correction once. Later arrivals containing the same proven payload cannot regain the rejected identity merely through rewritten metadata or compression.

**Why this priority**: A repaired library otherwise returns to the same wrong publication after another acquisition.

**Independent Test**: Register one independently verified correction, offer the same payload under the rejected identity with different metadata and compression, and confirm it stays held without changing either library owner.

**Acceptance Scenarios**:

1. **Given** a reviewed correction and current exact correct publication, **When** the operator records its evidence, **Then** the durable record binds that payload, its correct owner and rejected owner while preserving the correction history.
2. **Given** no reviewed correction, **When** archive metadata claims that a correction exists, **Then** that claim cannot create or change correction evidence.
3. **Given** changed or ambiguous correct-owner evidence, **When** registration is attempted, **Then** it stops without publishing a correction or changing media.

### User Story 2 — Hold repeated wrong publications before publication (Priority: P1)

Native and maintenance-worker imports, metadata changes, rescans and naming operations check verified correction evidence before they can assign a known payload to another publication. The source remains available for review.

**Why this priority**: Consistent but wrong filename and metadata cannot establish the actual publication.

**Independent Test**: Exercise each admitted writer path with the registered payload under the wrong owner, including disabled and legacy metadata policies, and verify no tagging, placement, owner/status change or cleanup occurs.

**Acceptance Scenarios**:

1. **Given** a known corrected payload offered under a conflicting owner, **When** automatic import or tagging runs, **Then** it retains the archive and reports publication review before mutation.
2. **Given** the same publication with changed compression or root metadata, **When** it is offered under the rejected owner, **Then** the same hold applies.
3. **Given** a genuinely different payload for the wanted issue, **When** ordinary import checks pass, **Then** the correction does not blacklist that issue, series or indexer.
4. **Given** stale, missing or malformed required correction evidence, **When** a guarded operation runs, **Then** it holds uncertain work without deleting originals or declaring completion.

### User Story 3 — Reconcile retained repeats without duplicate replacement (Priority: P2)

The operator can account for a repeated wrong archive while preserving the already verified correct library file, historical evidence and legitimate acquisition intent.

**Why this priority**: Existing repeats need repair as well as future prevention.

**Independent Test**: With an existing correct publication and retained incorrect duplicate, perform a scoped restore-verified reconciliation and prove the correct bytes, owner and reader remain intact.

**Acceptance Scenarios**:

1. **Given** an exact verified repeat and correct library copy, **When** reconciliation runs, **Then** the incorrect copy is retained outside scanned libraries and the correct copy is not overwritten or unnecessarily retagged.
2. **Given** uncertain acquisition provenance, **When** reconciliation finishes, **Then** it does not fabricate a failed-release binding or cancel legitimate wanted acquisition.
3. **Given** changed sources or owners, **When** reconciliation resumes, **Then** it stops against the recorded baseline rather than clearing an unrelated claim.

### Edge Cases

- Same payload with rewritten metadata, different compression, directory entries, sidecars or duplicate member names.
- Different page payload with the same issue label; a correction must not become a name blacklist.
- Linked, corrupt, oversized, changing or unsupported archives; unavailable correction state or ambiguous issue/annual owners.
- Correct files renamed or retagged through accepted journals; historical correction evidence must remain traceable.
- Interrupted registration/publication, concurrent native and worker admission, partial cleanup and restored application state.
- New acquisitions during an audit; inventory drift is evidence rather than successful full-library acceptance.

## Requirements

### Functional Requirements

- **FR-001**: Record corrections only through authenticated explicit operator admission of reviewed evidence; archive metadata cannot seed corrections.
- **FR-002**: Bind every correction to a bounded complete metadata-independent payload inventory, exact correct and rejected publication owners, and immutable evidence references.
- **FR-003**: Validate the correct publication and its current unambiguous library ownership before admitting correction evidence.
- **FR-004**: Keep admitted correction history durable and auditable across restart and backup/restore; conflicting registration must not overwrite earlier evidence.
- **FR-005**: Detect identical known payloads despite root metadata or compression changes, while distinguishing changed payloads and conflicting inventories.
- **FR-006**: Hold a known payload offered under a conflicting owner before native or worker tagging, status assignment, placement, naming, metadata repair or cleanup.
- **FR-007**: Apply the guard regardless of enabled, disabled or legacy metadata policies; conversion/import pathways must not bypass it.
- **FR-008**: Preserve every rejected or uncertain source and truthful review evidence without fabricating import completion.
- **FR-009**: Keep ordinary eligibility for unknown payloads and genuinely different releases; do not blacklist a whole issue, series, provider or endpoint.
- **FR-010**: Hold uncertain checks when required state, stable archive inventory or owner evidence is unavailable or malformed.
- **FR-011**: Reconcile existing wrong duplicates only after a scoped consistent backup and independent isolated restore verification; preserve the correct archive and compare recorded owners before any catalog changes.
- **FR-012**: Preserve existing reader safeguards and historical evidence; the user deferred a separate additional reading-progress audit.
- **FR-013**: Distinguish source delivery, published images, live rollout, per-file proof and whole-library acceptance. Live rollout requires authorized privileged access and completed backup, restore and owning recovery prerequisites.

- **FR-014**: Reader-owned repeat retirement must bind one complete finite native batch and the continuously verified stopped reader, preserve unrelated namespace/catalog/reader facts, and support exact rollback with retained originals and independently verified restore custody.
- **FR-015**: Durable negative-retirement pending state must hold every ordinary native, worker and archive preparation purpose until the exact owning aggregate proves terminal acceptance. Unknown interruptions cannot grant replay or clear the hold.

### Key Entities

- **Publication correction**: Reviewed immutable relationship between one verified payload, its correct owner, rejected owners and supporting evidence.
- **Payload inventory**: Complete bounded member identities, sizes and byte digests excluding root publication metadata; directories and sidecars have explicit semantics.
- **Guard decision**: Current candidate identity, matching correction and allowed or held result with evidence provenance.
- **Reconciliation receipt**: Recorded before/after state, preservation proof and exact owner comparison for one retained repeat.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Every tested known-payload conflict is held before publication across all admitted writer pathways, with zero source deletion or false completion.
- **SC-002**: Rewritten metadata and recompression cannot evade a registered correction; different eligible payload fixtures remain eligible.
- **SC-003**: All crash, restart, stale-owner and corrupt-evidence fixtures preserve prior correction history and affected archives.
- **SC-004**: Scoped live acceptance proves the correct publication’s bytes, owner and reader intact, the incorrect repeat retained outside the library, and no unrelated catalog changes.

## Assumptions

- This specification is prospective and separate from accepted release naming and pack-generation fixes.
- Existing authenticated operator admission, writer coordination, durable state and backup workflows remain authoritative. A one-time explicitly reviewed correction-state initialization precedes media admission; an initialized empty registry preserves ordinary behavior.
- Correction records are private application state; public examples contain no live paths, credentials or machine-specific correction payloads.
- Exact acquisition origin must be proven separately before release-specific failure reporting.
- Exact internal-name changes and perceptual/OCR equivalence are outside v1 matching; separately verified aliases are required.
- No operation needs additional privileged access until the user permits it again; source development and isolated verification may proceed.
