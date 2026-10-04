# Implementation Plan: Verified comic release naming

**Branch**: `codex/comic-release-naming` | **Date**: 2026-10-03 | **Spec**: [spec.md](spec.md)

## Summary

Use one dotted release-name renderer for conversion follow-up and the existing CBZ library. Resolve unique ownership through Mylar's native catalog/parser and embedded identity before planning. Apply same-folder names through a primary-key native API with a durable filesystem/catalog journal under shared writer coordination. Keep recovery copies until reader restoration and catalog proof succeed; never use renaming to resolve contradictory publication identity.

## Technical Context

**Language/Version**: Existing Python runtimes in the Mylar and comic-normalizer images.
**Dependencies**: Standard library, existing archive/tagger verification and writer protocol; worker `python3-xxhash` to verify Komga's XXH3-128 file hash.
**Storage**: Private native rename journal, worker proposals/receipts and temporary restore-verified copies; existing Mylar SQLite and library directories.
**Testing**: Focused unittest preservation/failure fixtures, actual native parser/API image gates, complete worker gate and repository validation.
**Platform**: Existing unprivileged Linux images, local writer state and NFS library files.
**Performance**: One rename per worker cycle by default; bounded bulk batches and streaming hash/CRC checks without image re-encoding.
**Constraints**: Same-folder no-overwrite moves, exact content and filesystem-attribute preservation, no new mounts/networks/secrets. Disabled policy preserves existing behavior. Reader hashes and ownership must be fresh and unique.
**Scope**: Watched primary issues and annuals with uniquely proven ownership. External sidecars, ambiguous editions and unsupported supplements remain for review.

## Constitution Check

Portable opt-in examples remain disabled. Change worker configuration examples, preparation validation, image dependencies, stack metadata and both owning READMEs together. Compose and ingress need no topology changes. No runtime credentials enter source or manifests. Source validation is read-only; live enablement/bulk migration uses explicit existing authorization and restore-verified application/media preservation. Regenerate catalog if metadata changes. No constitutional exceptions.

## Project Structure

- `stacks/mylar3/config/release_naming.py`: native ownership proof, journaled publication/catalog commit and recovery.
- `stacks/mylar3/config/patch_release_naming.py`: primary-key endpoints and native recovery integration.
- `stacks/komga/normalizer/release_naming.py`: release renderer and opt-in policy.
- `stacks/komga/normalizer/naming_worker.py`: reader-hash gate, proposals and worker/bulk receipts.
- Corresponding native/worker tests, image module inventories, configuration example, preparation validation, READMEs and stack metadata.
- `specs/022-comic-release-naming/`: prospective requirements, design, contract, tasks and acceptance evidence.

## Delivery and migration

Deploy compatible native and worker images with naming disabled first. Verify backups and service data. Enable dotted naming only after the native versioned capability is available. Preview a bulk manifest against current sources, catalog and reader hashes. Apply bounded entries while other metadata writers remain coordinated. Confirm exact bytes, catalog paths and reader progress, then remove only completed temporary media copies; retain journals/manifests and unresolved originals. Roll back pending path changes from verified copies and native journals before using an older image.

## Complexity Tracking

The user requested a combined bulk pass after the naming pilot. A bounded private
coordinator can retain the two existing naming preservation copies through links
within private state, then finish the reader move before metadata admission. It
never links the library file. A completed naming receipt can precede its temporary
copy cleanup; reconcile exact owned links before admitting metadata. The native
`apply_preserved` supplement entry point independently validates fresh source and
both retained copies, shares the ordinary publication/completeness verifier and
returns a durable token and before/after hashes. The coordinator journals that
token first, rebinds exact-path credit deferrals, verifies final catalog/payload/
reader state and owns cleanup. Failed or uncertain phases retain the shared set;
metadata changes never trigger replay of the earlier naming request.

No exceptions. A native journal is necessary because filesystem publication and SQLite location updates cannot be committed in one transaction. Reader restoration is independently asynchronous and must be proven before the worker reports completion.

## Pack evidence across publication

Live review at the completed 911-publication checkpoint found confirmed pack members still bound to their original destinations and file signatures. Preserve the strict presence check. Add a durable old-to-new binding intent to the native rename and metadata publication journals before mutation, then update all matching confirmed pack members after exact catalog/content validation and before clearing fences or deleting recovery copies. Atomic workflow-store updates and idempotent recovery must preserve unrelated records, sidecars, member states and cleanup history. Legacy journal compatibility must retain uncertain evidence rather than infer a transition. The standalone combined metadata companion must use the same native binding implementation.

## Explicit rejected-attempt recovery

Keep rejected native journals and worker review receipts immutable. An operator prepares a fresh version-2 request with the exact `retry_of` token after validating the original source, both retained copies and reader identity/progress. The native owner revalidates the predecessor, original inode/attributes/hash and active table/status/year, then stores its complete digest in a distinct child journal. Use ordinary fenced publication and reader restoration for the child. No tick automatically constructs replacements; uncertain children reconcile through their own token. Deploy matching native and worker support only after restore-verified state backups and independent review.
