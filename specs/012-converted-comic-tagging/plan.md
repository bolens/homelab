# Implementation Plan: Converted comic tagging

**Branch**: `codex/converted-comic-tagging` | **Date**: 2026-09-29 | **Spec**: [spec.md](spec.md)

## Summary

Extend the normalizer's durable notification with an opt-in primary-key API request after rescan. Store jobs in Mylar's existing workflow journal. Poll one due job from the native post-processing worker while its download queue is idle. Revalidate catalog ownership and file digest under the existing writer lock. Use Modern in-place publication with a stored token, recover that token first after interruptions, and fill missing metadata only. Show a separate durable conversion-tagging table.

## Technical Context

Python 3.10+ in pinned Mylar and normalizer images, SQLite workflow journal, existing ComicTagger runtime, native Mako/jQuery DataTables. Standard-library unit tests plus the existing offline image gates. Linux/NFS media with local private recovery state. No dependencies, ports, mounts, privileges or credentials added. The consumer performs at most one job per idle worker poll. All terminal conversion identities are retained as small records for duplicate suppression; UI shows 100 recent entries.

## Constitution Check

All five principles pass before and after design. Portable opt-in uses existing private normalizer configuration. Both stack documentation and preparation guidance explain consumer-first rollout and state retention. Existing Compose/security/ingress contracts remain unchanged. Validation is isolated. Live deployment includes verified state backup/restore, affected-file preservation, rollback and cleanup. No whole-library copy.

## Project Structure

- `stacks/mylar3/config/converted_tagging.py`: admission, catalog validation, durable worker and status.
- `stacks/mylar3/config/patch_converted_tagging.py`: checked API and worker integration.
- `stacks/mylar3/config/tagger_native.py`, `tagger_service.py`: explicit automatic in-place policy and persistent publication token.
- `stacks/mylar3/config/pp_monitor.py`, `post_processing.html`: status.
- `stacks/komga/normalizer/normalize.py`, `writer_cycle.py`: opt-in producer and independent notification retries.
- Corresponding tests, image verification registration, both stack contracts and docs.

## Delivery

Consumer first, producer second. Enable private `mylar.tag_converted` only after consumer health and preservation proof. Backfill selected verified missing-metadata receipts, not the whole library. Preserve application records and protected service identities. Retain backups if verification is inconclusive.
