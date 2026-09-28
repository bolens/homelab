# Implementation plan: Modern tagging and optional DDL transport

**Branch**: `codex/mylar-modern-tagger` | **Date**: 2026-09-28 | [Specification](spec.md)

## Summary

Expand with tested compatibility helpers, build an isolated pinned modern runtime,
then integrate it behind an explicit backend choice. Preserve the legacy backend
through a canary and rollback window. Evaluate optional DDL discovery separately.
Do not transplant either upstream PR wholesale.

## Technical context

Python 3.10 in the pinned LinuxServer base, stdlib unittest, generated CBZ fixtures,
Mylar config and workflow.sqlite, existing normalizer receipts. Candidate ComicTagger
is 1.6.0b11.dev0 with built-in `cr`; curl_cffi 0.16.3 is the discovery candidate.
Both require a resolved hash lock and target-platform build proof before installation.
No new service, port, mount, privilege or public route is required. Process limits:
version 10 seconds, tag 180 seconds, combined captured output 64 KiB. Archive metadata
input is limited to 256 KiB. No second conversion writer or parallel tagging pool.

## Constitution check

Before and after design: portable examples, private settings excluded, no live
mutation in fixture validation, pinned dependencies, normalizer ownership preserved.
The first increment adds build-tested helpers only: Compose, env example, preparation,
metadata and ingress contracts need no runtime changes. At backend activation, update
all affected contract surfaces together and regenerate catalog output if metadata changes.

## Project structure and ownership

- `stacks/mylar3/config/tagger_runtime.py`: bounded child execution and typed results.
- `tagger_metadata.py`: explicit overrides and conservative ComicInfo reconciliation.
- `tagger_archive.py`: bounded member verification and reconciliation into a new
  operation file. It never publishes over a source.
- `tagger_adapter.py`: inactive staged archive verification, atomic exchange owner
  and private versioned receipts. Integration must coordinate other media writers.
- Future `patch_modern_tagger.py`: checked native/manual routing and preference adapter.
- `archive_monitor.py`: receipts from verified results, not CLI banner interpretation.
- `stacks/mylar3/Dockerfile`: isolated venv copied with native ICU dependencies into
  final image. Never overwrite Mylar's Python dependency environment.
- Future `ddl_transport.py`: discovery session factory, exception normalization,
  resource lifetime; `verified_transfer.py` remains byte-download owner.
- Spec files: research, data model, contracts, acceptance, quickstart and tasks.

## Migration sequence

1. Implement and test process/metadata helpers without enabling a new backend.
2. Resolve/hash-lock the candidate and all transitive dependencies for the pinned
   base. Build headless without Qt. Run the real CLI and writer, offline, in final
   runtime layout. Version banner/exit behavior must be observed, not guessed.
3. Implement archive staging, page/member hashes, XML policy, source-race detection,
   permissions, fsync and atomic publication. Persist private recovery receipts and
   crash recovery before a source can be replaced. Reject unsupported inputs.
   Native manual tagging currently copies the returned temporary path over its
   destination and deletes that temporary file. Integration must replace that
  publication path, not return the original path into its cleanup branch. Automatic
   post-processing also consumes a temporary path, so its handoff needs separate proof.
   The fixture publisher now retains a displaced source via Linux atomic exchange.
   It refuses hardlinks and extended attributes/ACLs. An unsupported filesystem has
   no non-atomic fallback. Prove the real media filesystem and exclude other writers
   before native activation; conflict copies must not be deleted automatically.
4. Wire native automatic/manual tagging, annual identity, disabled tagging, overwrite
   settings and monitor outcomes. Legacy remains default; unsupported CBL writes are
   explicit and retain the configured preference. Do not auto-fallback after a write.
5. Prove matrix and both backend paths. Publish image; back up affected app state and
   each canary file, verify isolated restore, wait for active processing to clear,
   deploy only Mylar, canary generated fixtures, then selected real copies. Verify
   records/media and unrelated uptime. Retain old image until verification completes.
6. Independently add opt-in curl discovery. Requests remains archive transport. Full
   curl streaming needs a bounded-buffer design and every transport gate before use.

## Rollback and mixed versions

New settings are additive and legacy defaults remain intact. New receipt fields are
versioned; older observers must ignore optional fields. Store uncertain publication
intent before rename, reconcile source/destination hashes on recovery, and never
reissue a second tagger write blindly. Before native rollout, prove old image reads
new state and retains unknown settings. If not, restore verified app state with the
old image. Restore only affected canary files. No bulk-library backup for routine
updates. Remove operation backups only after successful forward or rollback proof.

## Alternatives and risks

Built-in `cr` lacks StoryArcNumber assignment and can overwrite notes/pages from its
metadata object. Preserve unsupported fields explicitly. Optional CIX/archived-tag
plugins add dependencies and different schemas, so assess separately rather than
installing all extras. CLI success is not archive success. Conversion-only native
behavior cannot simply be deleted before routing callers. Curl's unbounded stream
queue and different timeout semantics block immediate full transport replacement.
