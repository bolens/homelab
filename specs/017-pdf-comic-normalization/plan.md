# Implementation Plan: PDF comic normalization

**Branch**: `codex/pdf-comic-normalization` | **Date**: 2026-09-29 | **Spec**: [spec.md](spec.md)

## Summary
Add a modular PDF reading-derivative adapter to the existing normalizer. Poppler renders bounded PNG pages; the existing archiving-utils tool inventories and validates the CBZ. Original PDF and settings-bound checksummed receipts remain in normalizer state. Existing import recovery receives a verified CBZ copy. No new tagging owner or download transport.

## Technical Context
Python 3 on the pinned Debian archiving-utils image; distribution poppler-utils and python3-pil dependencies. Serial PDF rendering from preserved copies outside the shared writer; publication/import stays guarded. Local recovery state, no schema migration, no new mounts/network/privileges. Real Poppler fixture tests plus existing archive suites. Default 3200-pixel long edge; max 1000 pages and existing expanded-byte budget. Total conversion budget 600 seconds. Refuse encrypted PDFs. Cached originals are never automatically deleted by PDF maintenance.

## Constitution Check
Pass before and after design: opt-in portable config; complete stack documentation and examples; existing mounts and least privileges; scoped verified backup/rollback; generated catalog from source. Preparation preserves existing settings. Existing archive semantics remain byte-preserving; PDF rasterization is documented separately.

## Project Structure
`stacks/komga/normalizer/pdf_conversion.py` owns rendering, derivative cache and preservation receipts.
`normalize.py`, `maintenance.py`, `import_recovery.py` route eligible PDFs through it; pack recovery uses the existing common converter interface.
`stacks/mylar3/config/converted_catalog.py` recognizes PDF-to-CBZ location repair. Mylar verified_transfer uses image-bundled Poppler to validate completed PDFs, with actual transfer/pack regressions. Deploy Mylar before enabling the worker policy.
Tracked Komga contracts document dependencies and opt-in. Tests cover real rendering and existing recovery flows.

## Rollout and rollback
Build/test first. Verify cached books read-only in an isolated canary. Back up and restore-check worker state/config; preserve the two source PDFs only, not the whole library. Quiesce only idle normalizer under shared writer, deploy pinned published image with all existing overrides. Verify originals, page inventories, catalog/import state, reader health and other container identities/uptime. Retain backup on uncertainty; roll back verified state/config/image on real loss. Remove only operation backups on success. Never promote an active partial download.
