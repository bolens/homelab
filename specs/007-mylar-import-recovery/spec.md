# Feature Specification: Automatic recovery of unmatched comic imports

**Created**: 2026-09-24

**Status**: Implemented and verified

**Input**: Automatically handle “No unique issue match” on Import problems.

## User Scenarios & Testing

### User Story 1 — Recover identifiable comics (Priority: P1)

A completed comic with a unique, supported identity is matched and submitted for
post-processing without manual filename edits. Original downloads remain available
until existing verified duplicate cleanup proves the library contains their data.

**Independent test**: A settled comic with an exact issue identifier or an exact
series/year/issue match is submitted once; a second maintenance cycle does not
submit it again.

### User Story 2 — Retain ambiguous comics (Priority: P1)

Conflicting identifiers, ambiguous editions, unsupported formats, and missing
identity information remain visible for review without speculative imports.

**Independent test**: Two plausible editions produce no submission. An uncertain
submission response remains visible and does not cause an automatic retry.

## Requirements

- Recover only uniquely identified regular issues already tracked by Mylar.
- Support explicit issue identifiers, bounded readable comic metadata, and strict
  title/year/issue filenames. Do not use fuzzy title similarity as proof.
- Never overwrite an already downloaded issue through automatic recovery.
- Validate archives and preserve original bytes before submitting a separate copy.
- Submit at most one recovery per maintenance cycle while post-processing is idle.
- Remember attempts across restarts; report queued and review-required states.
- Keep credentials, filesystem paths, and download URLs out of public reports.
- Require explicit deployment path mapping and enablement; portable examples default off.

## Success Criteria

- Every supported unambiguous fixture is matched; every ambiguous fixture is retained.
- Repeated cycles and interrupted responses submit a given source at most once.
- Original source hashes remain unchanged by recovery submission.
- Import problems distinguishes automatic submission from confirmed library import.

## Assumptions and scope

Regular issues and Mylar-supported CBZ/CBR imports are in scope. Annuals, packs,
fuzzy guesses, adding new series, and changing conversion ownership are excluded.
The existing normalizer continues to own its current post-import conversion work.

## Key Entities

Completed comic, identity evidence, tracked issue, recovery copy, durable attempt.
