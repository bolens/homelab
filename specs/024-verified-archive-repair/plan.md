# Implementation Plan: Verified archive repair

**Branch**: `codex/comic-worker-decoder` | **Date**: 2026-10-08 | **Spec**: [spec.md](spec.md)

## Summary

Install bounded refusal diagnostics first, then a dedicated native-owned preparation/adoption route for one lossless ZIP directory-spelling repair. Ordinary inventory, nested metadata lineage, correction policy and import acknowledgements retain their current meaning. A diagnostic or prepared copy cannot authorize publication.

## Technical Context

- Runtime: the existing Mylar and normalizer Python images; actual selected-runtime checks include Mylar Python 3.10.
- Dependencies: existing publication guard, native Controller, existing-only shared Writer, complete correction census and native/reader transaction boundaries. No new external dependency.
- Storage: private preparation, custody and phase records inside existing application state, outside scanned media. No extra mount or automatic remote directory creation.
- Tests: disposable byte, SQLite and filesystem controls; source/image imports, native/generated parity, late-change/lost-response controls and verified scoped live acceptance.
- Limits: 128 MiB for buffered runtime diagnostics within the existing 768 MiB worker allowance, 512 MiB source for owned native repair preparation, existing 4,096-member/4 GiB expanded/per-member/metadata limits and monotonic deadlines. No remote access during classification or while Writer is held.
- Profile: one empty stored Unix directory with consistent directory flag and missing slash in a closed ZIP32 archive. Other ordinary supported variants stay on ordinary inventory.

## Constitution Check

Portable examples contain no private archive paths, identities, reader rows or credentials. Inspect Compose, environment, metadata, preparation, ingress and README together; diagnostics add no settings, mounts, privileges, ports or runtime dependencies. Existing-only state and writer ordering remain mandatory. Live adoption requires measured consistent affected-state backup, independent restore, custody, actual reader/native verification and compatible rollback. Source, image and live acceptance are separate. One integration owner handles tracked files, Git, generators and live operations.

## Project Structure

Native modules: `stacks/mylar3/config/publication_archive_{layout,derivative,repair,diagnostics}.py` and owning tests. `publication_native.py` invokes diagnostics only after direct ordinary inventory refusal. `scripts/sync-publication-reader.py` generates exact worker copies; `stacks/komga/normalizer/publication_guard.py` preserves terminal refusal. Native installation, image verification, workflow diagnostic capability and normalizer Dockerfile change together.

Dedicated native preparation/adoption belongs in `publication_archive_owned.py`, its tests, `publication_api.py` and actual processing/reader boundaries. Reuse reviewed conversion/reader primitives only where their contracts match; never widen nested lineage or generic worker import permission.

## Design and Delivery

US1 independently delivers confined stable-source classification with fixed status/reason and terminal refusal. Valid ordinary verification skips it. Catalog, owner and admission failures cannot trigger it.

US2 captures actual source/witness, current owner/catalog/census and custody under Writer, writes an exclusive private derivative, fsyncs and independently inventories readback. Seal every source/stage/custody/ancestor fact before returning non-executable preparation.

US3 creates the dedicated same-payload repair capability only after current allowed-owner/correction and exact reader continuity checks. Exceptional original inventory applies only to the captured source; other owner archives retain ordinary verification. Durable predecessor/phase binding prevents unverified replay or acknowledgement. Native/reader acceptance precedes cleanup.

Features 022/023 complete current-library acceptance still gates general writer release. Do not recreate Mylar while claiming a process-local startup hold survives. Diagnostics or private copies alone cannot release it.
