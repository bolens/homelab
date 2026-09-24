# Verification evidence

## Completed checks

- The pinned Mylar image passed 66 tests, including processing lifecycle,
  queue preservation, exception propagation, bounded observations, archive format
  detection, metadata comparisons, report privacy, and patch compatibility.
- The pinned converter image passed 36 normalizer and maintenance tests.
- The monitor JavaScript passed Node syntax checking.
- `make validate`, focused Markdown checks, and `git diff --check` passed.
  Compose validation skipped only the externally generated PostHog bundle.
- Before deployment, verified application-consistent backups and isolated restores
  for 565 Mylar files and 59 normalizer files, including database integrity.
- Recorded 670 existing library files by size and modification time.
- The new live snapshot endpoint returned HTTP 200 with processing enabled,
  an available worker, and an idle queue after startup settled.

## Live acceptance completed

Authenticated Chromium verified navigation from Manage, DDL Queue Management, and
Import problems; refresh-action theme parity; actual queue snapshots; escaped
fixture text; active/failure/conversion/metadata displays; preserved pagination;
stale-warning recovery; and non-overlapping polling. Both external routes reject
anonymous access. No unexpected HTTP or JavaScript errors remained.

Browser verification found and fixed a cache-busting query parameter rejected by
CherryPy, a refresh-button theme mismatch, and missing page identity for shared
completion notifications. Custom report tables are excluded from native AJAX reloads.

The maintenance worker resumed. All 670 baseline library files and 13 retained
originals passed preservation checks; databases remained readable with their
original IDs; credentials remained unchanged; both Kuma monitors were UP.
The temporary monitor backup and isolated restore copies were removed after success.
The result is recorded in `/tmp/pp-monitor-final.json`.
