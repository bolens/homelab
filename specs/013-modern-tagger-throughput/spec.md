# Feature Specification: Modern tagger throughput

**Feature Branch**: `codex/modern-tagger-throughput`

**Created**: 2026-09-29

**Status**: Ready for implementation

**Input**: User request: another modern tagger optimization pass.

## User Scenarios & Testing

### User Story 1 - Tag consecutive issues faster (Priority: P1)

An operator tagging several issues from the same series avoids repeatedly fetching unchanged series information.

**Why this priority**: Pack and backfill jobs repeat series requests, each with provider latency and a configured wait.

**Independent Test**: Tag two distinct issues from one series with a controlled provider and compare requests and resulting metadata.

**Acceptance Scenarios**:

1. Given recent validated series information, when the next issue is tagged, then its issue information is fetched fresh and the matching series information is reused.
2. Given expired information or changed provider credentials or connection settings, when another issue is tagged, then series information is fetched afresh.
3. Given a wrong issue or series identity, when tagging is requested, then incorrect metadata is never accepted.

### User Story 2 - Preserve existing tags with less disk work (Priority: P2)

An operator preserving existing metadata avoids copying the comic solely to report that it is unchanged.

**Why this priority**: Already-tagged rescans should not reserve or write several archive-sized temporary files.

**Independent Test**: Preserve a tagged comic while forbidding archive-copy creation; verify a replayable unchanged result and identical content and attributes.

**Acceptance Scenarios**:

1. Given valid existing metadata and overwrite disabled, when preservation runs, then no archive-sized backup is written and no provider or tagger call occurs.
2. Given a concurrent file change, corruption, or interrupted operation, when preservation finishes or recovers, then it must not report an unverified success or discard the source.

### Edge Cases

Expired or malformed cache entries, oversized provider values, credential changes, different annual release volumes, process restart, low free space, concurrent cache callers, stale publication tokens, and source replacement during unchanged processing.

## Requirements

### Functional Requirements

- **FR-001**: Every issue lookup MUST remain fresh and validate the requested issue and release-series identities.
- **FR-002**: Reused series information MUST expire within 300 seconds, without renewal on reads, and be isolated by provider endpoint, credential, and TLS verification policy.
- **FR-003**: The cache MUST retain at most 64 entries of at most 16 KiB each, only in memory. Failures and malformed results MUST NOT populate it.
- **FR-004**: Actual provider requests MUST retain configured pacing, bounds, deadlines, and secret-free diagnostics.
- **FR-005**: Existing-metadata preservation MUST avoid archive-sized staging while retaining full content, identity, attribute, durable receipt, and recovery verification.
- **FR-006**: No backend preference, metadata overwrite policy, reader follow-up, conversion behavior, or service exposure may change.
- **FR-007**: Regression and measured acceptance MUST cover the cache boundary and unchanged publication path before delivery.

### Key Entities

- Recent series information: validated public provider data, isolated origin, original expiry.
- Unchanged tagging receipt: durable proof that the original comic and its metadata were preserved.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Two consecutive distinct issues in one series require three provider requests instead of four; a ten-issue batch requires eleven instead of twenty while entries remain valid.
- **SC-002**: Preserving an already-tagged comic writes zero archive-sized staging copies, with identical source content and attributes.
- **SC-003**: Wrong identities, changed credentials, expired information, corruption, and source races do not produce incorrect metadata or unverified success.
- **SC-004**: Controlled before/after timings and work counts are recorded; live speed claims are separated from synthetic measurements.

## Assumptions

Series information may be up to five minutes old; issue details remain fresh. Operators retain the existing configured provider pacing. This pass does not weaken archive verification or add tagging parallelism. Live updates remain Mylar-only, with verified app backups and no full-library copy or real power-loss test.
