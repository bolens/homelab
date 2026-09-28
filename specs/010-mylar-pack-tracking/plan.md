# Implementation Plan: Verified pack tracking and recovery

**Branch**: `codex/mylar-pack-tracking` | **Date**: 2026-09-28
**Spec**: [spec.md](spec.md)

## Summary

Add durable member inventory and recovery to the existing Mylar/normalizer integration. Fix native annual lookup and processing ownership first, then add conservative classification, catalog reconciliation, preservation receipts, and authenticated visibility.

## Technical Context

Python Mylar build-time source patches and standard-library modules; existing SQLite workflow journal. Optional Python maintenance worker owns archive conversion and content checks using the pinned archiving-utils image. Existing mounts and primary-key API are reused. No new service, network, port, credential or concurrency.

## Constitution Check

Public examples stay portable and automatic content recovery remains opt-in. No live paths or credentials enter tracked fixtures. Compose, preparation, examples, metadata and documentation are reviewed together; unchanged access/mount contracts are documented rather than expanded. Native issue status changes require confirmed identity. New persistent records stay in existing backed-up state. Focused disposable tests, image gates and full repository validation precede publication.

## Source Ownership

- `stacks/mylar3/config`: checked annual/lock/pack status hooks, catalog API, persistent pack/supplement records, existing authenticated UI.
- `stacks/komga/normalizer`: bounded pack inventory, exact matching, conversion, supplement preservation, source-version receipts and worker reports.
- Stack READMEs/examples/preparation/metadata: opt-in behavior and backup/delivery contract.
- `specs/010-mylar-pack-tracking`: prospective acceptance and evidence. The first narrow annual/lock regression was implemented while confirming native seams; remaining design precedes pack implementation.

## Verification and Deployment

Use synthetic regular/annual/cover/digital/nested/corrupt fixtures, with real archive tool validation for preservation. Exercise retries and process exits. Check source patch idempotence against the pinned image. Run focused tests then `make validate` and strict delivery gates. Publish through a checked PR and main-only GHCR workflow.

For live deployment, first refresh idle/download state. Back up affected config/databases/worker state and media at risk, verify isolated restores and hashes, then update only changed services. Never stop NZBGet or Komga. Do not interrupt active DDL/processing or normalizer operations. Verify baseline records/files and Uptime Kuma; automatically roll back missing/corrupt data. Retain backup on inconclusive verification; remove task backup only after success.

## Complexity Tracking

Member state is separate from native issue status so supplements and missing catalog entries cannot masquerade as full issues. Keep durable pack records independent of transient DDL history. No generic new job framework.
