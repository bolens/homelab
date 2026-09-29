# Implementation Plan: Modern tagger throughput

**Branch**: `codex/modern-tagger-throughput` | **Date**: 2026-09-29 | **Spec**: [spec.md](spec.md)

## Summary

Add a bounded process-local volume cache around the existing private lookup worker. Fresh issue responses still identify and validate the expected release volume. Cache entries are scoped by a hash of endpoint, credential and TLS policy, have an original 300-second deadline, and are never persisted. The child rechecks expiry after the issue request. Separately, finish preserve-existing publication after durable intent and source verification, before any archive-sized staging or disk-space reservation.

## Technical Context

Python in the existing Mylar image; no dependency changes. Requests and the bounded subprocess runner remain. Existing unittest fixtures, the pinned image gate and controlled loopback provider cover behavior. Cache limits: 64 entries, 16 KiB per entry, 300-second non-sliding TTL. Existing v1/v2 publication receipts retain their schema and recovery paths.

## Constitution Check

Portable examples, private credential files, read-only validation, and current exposure/persistence contracts remain intact. Compose, environment example, metadata, preparation and ingress were inspected: no field, mount, network, privilege or preparation change is required. README owns the new transient freshness behavior. Requested Mylar deployment requires verified application backup and isolated restore, idle/writer checks, preservation and health proof, and rollback on loss. NZBGet, Komga and the normalizer stay running. No full-library copy or real power-loss test.

## Project Structure

- `stacks/mylar3/config/tagger_volume_cache.py`: cache bounds, context isolation and expiry.
- `tagger_lookup.py`: private worker request/response, fresh issue validation and cache use.
- `install_tagger_service.py` and `verify_image.py`: package inclusion and image gate.
- `tagger_adapter.py`: unchanged publication before staging.
- Relevant `test_tagger_*.py`: cache, subprocess, publication, NFS and native regressions.
- `stacks/mylar3/README.md`: transient cache behavior and preservation fast path.

## Validation and delivery

Measure two-issue provider calls and a repeated 64 MiB archive fixture before/after. Test expiry, credential/TLS/endpoint isolation, bounds, malformed responses, actual child execution, annual identity, no-overwrite disk writes, source races, and interruption recovery. Run focused tests, image gates, `make validate` and required strict checks. Obtain independent reviews, merge through GitHub checks, verify GHCR publication, deploy only Mylar and record preservation proof.

Post-design constitution check passes. No new public API, persistent schema, runtime setting or dependency is introduced.
