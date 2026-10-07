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
  config/publication_guard.py config/publication_api.py
  config/patch_publication_guard.py config/patch_publication_startup.py
  config/publication_fresh.py config/publication_native.py config/publication_transaction.py
  config/patch_publication_processing.py config/test_publication_native.py
  config/test_publication_guard.py config/test_publication_api.py
  config/test_publication_startup.py
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

**Structure Decision**: Keep correction authority in the focused native SDK, authenticated protocol in its separate controller and checked build adapter, and the worker protocol adapter in its independent Docker build context. Integrate checks into owning modules and actual native branch patches. Preserve existing owner/recovery contracts instead of introducing a new general processing framework.

## Delivery and verification

Implement and verify registration as the first independent story, then every publication boundary, then scoped repeat reconciliation. Source delivery may be split at coherent reviewed milestones; do not call prevention complete until all writer boundaries and matching images pass. Native-first rollout is coordinated and restore-verified; exact existing repeats seed only reviewed evidence. Feature 022 completion remains gated by current-library repair, final protected second pass, cleanup and worker resumption.

## Owned tagging integration

T007 introduces a private typed tagging intent and internal capability under the
already admitted raw Writer. Ordinary operations and public advisory routes keep
their pending-state hold; only the exact current job may revalidate its own fence
and payload. Bind native tagger state-directory identities before producer use.
Persist source/owner/policy/census and phase-specific publication evidence with its
receipt. Recheck current authority and matched correct-owner archives before
publication, pack finalization, cleanup and acknowledgement. Clear only the
captured fence after durable verified terminal receipt; interruptions retain the
typed hold and preservation copies for explicit review. This requires shared Publisher/NFS/
handoff checkpoint work during T007; T009 subsequently covers its other direct
consumers and reviewed source-to-target/derivative recovery. No generic nested
fence bypass or automatic upgrade of unbound receipts is permitted. T010 must also
hold a retained prepared tagging intent even when its pending marker is absent.
Legacy copy/CLI/cleanup remains held before invocation in publication mode until
its temporary state and fallback placement are bound to an owned adapter.

An in-place producer may replace only a retained copy outside the registered
correction owner paths. Bind its
complete NFS before/after file and workspace facts into both the owned intent and
receipt before displacement. Preserve the current registered archives and complete
payload/owner observations throughout. Passive proof uses only the already-bound
in-process publisher; expired capabilities and lost state grant no initialization
or replay. Registered catalog paths require an explicitly adopted exact derivative relation and a typed producer; the new reviewed transition preserves original payload protection and every inherited owner claim. Unadopted SDK or automatic nested repair remains held.

Keep terminal witnesses under the existing private writer state. Bind their
complete retained predecessor to the receipt's canonical intent digest, and bind
terminal facts to a canonical proof in that same receipt before releasing the
owned marker. Revalidate witness contents through both release boundaries.
An exact closed receipt may then be read by a later job without replay or a
remaining disposable output. Its epoch must still match current authority, its
revision cannot exceed the current revision and its census keys must remain
present. The receipt binds the complete original census; changed or unbound history stays
held. These witnesses grant no current media mutation or recovery permission.
