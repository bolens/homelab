# Implementation Plan: Completed comic reader scans

**Branch**: `codex/komga-completed-addition-scans` | **Date**: 2026-09-29 | **Spec**: [spec.md](spec.md)

## Summary

Add an opt-in normalizer module that observes Mylar catalog changes under the shared writer lock, waits for stable tagged CBZs and settled receipts, then batches authenticated Komga scan requests after releasing the lock.

## Technical Context

Python standard library in the existing pinned converter image. Existing Mylar read-only SQLite mount, Komga Reader client and media-writer protocol. Private atomic JSON journal plus status in existing normalizer state. No new service, mount, port, privilege, dependency or credential. Unit fixtures use disposable catalogs, archives, mocked HTTP and clocks. Full worker image gate covers integration.

Observe catalog rows once per successful conversion cycle. Baseline old catalog paths without archive reads. Inspect at most 50 pending new paths per cycle, rotating delayed candidates, using stat, bounded ZIP central directory and bounded ComicInfo only. Global five-item threshold, five-minute tail flush and two-minute minimum dispatch interval are configurable. Request only matching Komga library IDs. Save pacing before HTTP and acknowledged subsets afterward; timeouts can repeat an idempotent scan after the interval.

## Constitution Check

Pass before/after design: portable opt-in examples; same existing permissions and secrets; normalizer-only authorized rollout with verified backup and isolated restore; no library backup or media mutation by notifier; tests and generated docs checked. No exceptions.

## Project Structure

- `stacks/komga/normalizer/reader_scan.py`: policy, catalog readiness, journal, batching and targeted dispatch.
- `normalize.py`, `writer_cycle.py`: lifecycle and health integration.
- `test_reader_scan.py`, `test_writer_cycle.py`: acceptance boundaries.
- Existing stack README, example config, preparation, image and metadata contract.

## Delivery

Separate review, focused checks, complete image gate and repository gates precede PR merge/GHCR publication. Back up normalizer state and config, restore/verify independently, compare library and Mylar baselines, update only comic-normalizer with --no-deps. Preserve current container mounts/environment. Keep reader, Mylar and download-client uptime unchanged. Retain backup if preservation is inconclusive; rollback on confirmed loss/corruption. Enable only after baseline acceptance. Use an isolated durable notification fixture against one existing library for a bounded real scan, not artificial downloads or media edits.
