# Implementation Plan: Verified publication corrections

**Branch**: `codex/verified-publication-corrections` | **Date**: 2026-10-04 | **Spec**: [spec.md](spec.md)

**Input**: Prospective requirements from `specs/023-verified-publication-corrections/spec.md`.

## Summary

Preserve independently verified correction knowledge so repeated publication payloads cannot regain a wrong owner through filenames, metadata or recompression. Native Mylar owns authenticated immutable evidence and final admission; worker checks are advisory until local writer/revision checks and native publication revalidation pass. Existing incorrect duplicates remain separate restore-verified operational work.

## Technical Context

**Language/Version**: Existing Python native and worker runtimes; actual pinned image gates are authoritative.

**Primary Dependencies**: Existing Mylar workflow/writer/catalog/tagger modules; immutable archiving-utils artifact already used by the normalizer; image-bundled libarchive reader. No runtime network dependency for payload verification.

**Storage**: Existing private `workflow.sqlite`, complete correction census/revision and an owned writer-protocol binding marker; worker receipts in existing state. Native application schema is unchanged.

**Testing**: `unittest`, actual patched native-source branch checks, converter-backed worker fixtures, both published image build gates and `make ci-local`.

**Target Platform**: Independent portable Mylar and Komga Compose examples with the existing shared media/writer protocol.

**Project Type**: Native application adapters plus maintenance worker and authenticated operational APIs.

**Performance Goals**: No library-wide scan per import. Skip payload scans when the validated registry is empty; otherwise stream only the candidate and any matched correct-owner evidence, with fixed bounds/timeouts. Reuse only stable source/registry-bound proofs under writer exclusion.

**Constraints**: No guessed identities, archive writes during checks, automatic correction registration, false import completion, global blacklist or privilege expansion. New mounts/ports are unnecessary.

**Scale/Scope**: At most 512 immutable correction attestations per v1 registry; at most eight explicit allowed/rejected owners per admission; 4,096 archive members and 4 GiB expanded bytes per bounded inventory. Oversized or unavailable evidence remains held.

## Constitution Check

- Portable examples: private correction attestations remain runtime state; examples contain placeholders only.
- Complete contracts: Mylar image/runtime dependency, Compose/environment/preparation/ingress comments, metadata/README and module map are reviewed together; matching worker contracts document protocol, deployment and retention. Existing ports/mounts/privileges remain sufficient.
- Operations: registration and repair follow scoped consistent backup/independent restore; no privileged action while the user’s hold applies.
- Generated truth: regenerate catalog/topology only if tracked metadata changes; no manual generated edits.
- Validation: focused kernel/boundary/fixture checks, independent reviews, full local CI and actual native/worker image gates precede delivery.

Pre-research and post-design gates pass; no constitution exception is required.

## Project Structure

```text
specs/023-verified-publication-corrections/
  spec.md plan.md research.md data-model.md quickstart.md tasks.md
  contracts/publication-corrections.md checklists/requirements.md
stacks/mylar3/
  Dockerfile
  config/publication_guard.py
  config/patch_publication_guard.py
  config/test_publication_guard.py
  config/apply_patches.py config/verify_image.py config/MODULES.md
  config/{native_writers,workflow_store,processing_guard,tagger_backend,tagger_native,
          tagger_service,file_identity,converted_catalog,converted_tagging,
          release_naming,tagger_supplement,patch_media_writers,library_metadata,
          tagger_adapter,tagger_nfs}.py
stacks/komga/normalizer/
  publication_guard.py test_publication_guard.py
  import_recovery.py pack_recovery.py maintenance.py normalize.py naming_worker.py
  writer_cycle.py test_writer_cycle.py
```

**Structure Decision**: Keep the correction authority in one focused native module/build adapter, and the worker protocol adapter in its independent Docker build context. Integrate checks into owning modules and actual native branch patches. Preserve existing owner/recovery contracts instead of introducing a new general processing framework.

## Delivery and verification

Implement and verify registration as the first independent story, then every publication boundary, then scoped repeat reconciliation. Source delivery may be split at coherent reviewed milestones; do not call prevention complete until all writer boundaries and matching images pass. Native-first rollout is coordinated and restore-verified; exact existing repeats seed only reviewed evidence. Feature 022 completion remains gated by current-library repair, final protected second pass, cleanup and worker resumption.
