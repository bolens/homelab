# Validation: Completed comic reader scans

## Implementation evidence

The acceptance suite covers initial baseline without archive reads, five-item batching,
five-minute tail flush, minimum interval across restart, API failure retention,
partial library acknowledgments, unique library targeting, deleted/ambiguous catalog
entries, linked/missing/changed files, malformed/nested/oversize metadata, pending
tagging and conversion receipts, corrupt state, the 50-file inspection budget, and
metadata-only archive reads. Writer integration tests cover lock ownership,
after-release HTTP, busy and recovery deferral, and independent notification failures.

The complete normalizer suite passed 127 tests with the pinned archiving-utils
executable enabled in a disposable container; no tests skipped. `make validate`
passed (the existing externally generated PostHog bundle is intentionally skipped).
`make ci-local` passed, including hooks and history secret scanning. Remote CI,
published-image and live evidence belong to the delivery receipt.

## Review

Separate self-review covered the configuration/example/preparation contract,
SQLite native field names and annual semantics, converted-tag and metadata-repair
journal producers, normalizer receipt lifecycle, shared writer admission, bounded
ZIP reads, durable pacing, partial acknowledgments, health reporting, image COPY,
and rollback scope. No outstanding code findings. Independent agent review was
not used. Deployment and live API acceptance remain pending at this revision.

## Operational acceptance

Before activation, back up and restore-check only affected normalizer state and
configuration, preserving directory identities used by writer coordination.
Retain the media library in place. Establish an existing-catalog baseline without
scan replay, verify an accepted targeted scan with isolated notification state,
and compare preserved state/media plus uninterrupted protected-service uptime.
Do not claim asynchronous Komga analysis has finished merely from a successful
HTTP request. Keep private operational receipts outside Git.

## Live acceptance correction

The first image accepted a real targeted scan with isolated notification state,
without changing the comic hash or scheduled scans. Production startup exposed
unnecessary global deferral behind active media work. Initialize the catalog-only
baseline under the process lock before media admission, and inspect readiness
under the shared writer lock even when unrelated conversion receipts are pending.
Per-path receipt exclusion still prevents unfinished comics from counting.
Regression tests cover startup without archive/API access, restart without
rebaselining, and a completed batch alongside an unfinished conversion.

The corrected suite passed all 129 tests with archive conversion enabled and no
skips. `make ci-local` passed. Separate self-review traced startup ownership and
per-path exclusion through the active-conversion and reader-request boundaries.
