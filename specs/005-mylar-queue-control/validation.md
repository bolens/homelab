# Verification evidence

Date: 2026-09-24

## Isolated checks

- The pinned Mylar image passed all 49 tests, including retries, cooldowns,
  recovery, interrupted transfers, archive validation, authenticated views,
  escaping, and search fallback coverage.
- The pinned converter image passed all 24 maintenance and normalizer tests.
  The test container used the same 256 MiB temporary filesystem as CI.
- Node parsed the updated queue page script successfully.
- `make validate` and `git diff --check` passed. Compose validation rendered
  214 stacks without failures and skipped the externally generated PostHog bundle.
- A real retained RAR archive passed validation with Mylar's bundled decoder
  after deployment.

## Deployment and live behavior

- Stopped affected workers before backing up application configuration and state.
  Verified isolated restores against all 555 Mylar files and 56 normalizer files,
  and checked database integrity before deployment.
- Captured SHA-256 hashes for 660 original library archives, totaling 45.67 GiB.
- Mylar automatically restored 114 waiting downloads after recreation without
  manual requeueing.
- Live observations showed useful downloaded bytes increasing and completed
  downloads increasing from three to five. Downloaded issue records increased
  from 661 to 663, and the post-processing queue drained.
- All 118 sampled queue rows contained progress diagnostics. The import-problems
  page required login and rendered successfully with an authenticated session.
- Mylar, Komga, the maintenance worker, and Uptime Kuma reported healthy.
  The maintenance report was current.

## Preservation and cleanup

- Rehashed all 660 original library archives after deployment. Every SHA-256
  matched the baseline.
- Verified database integrity, preservation of original comic, issue, and annual
  record IDs, and unchanged credential settings without printing their values.
- Verified the interrupted partial copies and 12 prior recovery originals.
- Both Mylar Workers and Comic Maintenance monitors were UP in Uptime Kuma.
- Removed temporary backups and isolated restore copies after all checks passed.
  Retained recovery originals remain available outside the library scan roots.

## Search investigation

The installed search code already tries queries without the publication year.
Read-only probes for Scooby Apocalypse returned two articles with the year and
five without it, including the collected editions. Pokemon probes returned no
articles, which does not establish a matching regression. Existing matching rules
remain unchanged, with regression coverage for the fallback query sequence.

## Retrospective

Native downloader success must be followed by archive validation before import.
Mylar bundles its RAR decoder under its own library directory, so host-only tests
cannot establish that the deployed validator can read RAR files. The image gate
and a real retained archive verified that dependency.

Full library hashing over NFS dominated preservation verification. A persistent
verified inventory could reduce future checks to new or changed files, with
periodic full reads to detect corruption that file metadata does not reveal.
This feature does not implement that inventory.

## Follow-up: completed-import status and navigation

- Fixed stale retry text by reading current imported-issue state on each queue
  poll. A completed individual download whose issue is Downloaded with a library
  location now shows **Post-processed; in library**. Pack completion is not inferred
  from one member. Finished downloads show attempts used without a retry budget
  or provider cooldown.
- Added **Import problems** to the main Manage page. Both directions between
  Import problems and DDL Queue Management use the existing toolbar styling.
- All 51 Mylar image tests passed. A JavaScript execution check verified completed,
  retrying, and legacy rows. `make validate` passed.
- Verified a stopped-service application backup through an isolated restore before
  deployment. After deployment, the reported completed issue showed the new completed-import status with one attempt.
- Authenticated requests verified the Manage link and both toolbar links. The
  import page still required login. Mylar and the maintenance worker were healthy.
- Verified application record IDs, database integrity, unchanged configuration,
  all 666 existing library files by size and modification time, and the reported
  comic by SHA-256. This display-only follow-up did not repeat the full library
  hash audit. Removed its temporary backup and restore copies after verification.

## Follow-up: rendered button and table verification

The earlier HTML check did not establish rendered toolbar styling. Chromium
confirmed that Import problems lacked `initActions()`, leaving its return link
without the jQuery UI button classes and icon. The page also lacked the DataTables
script and stylesheet used by other management pages, causing a JavaScript error.

Added the shared toolbar initialization, table assets, and DataTable initialization
with search, sorting, pagination, and an empty-state message. Deployed only the
template after verifying its backup and isolated restore. No service restart or
application-data edit was needed.

Authenticated Chromium checks at 1440 by 900 confirmed matching button classes,
font, border, corner radius, background, and icon presence on Manage and Import
problems. Inspected both button screenshots and the rendered table. Search,
sorting, and the empty state passed browser checks, with no page JavaScript errors.
This supersedes the earlier markup-only styling evidence.

## Follow-up: clearer status and recovery controls

Renamed the queue column to **Download / import status**. Completed items now show
their status without an attempt suffix, while the historical attempt count remains
in a tooltip. Active retries retain the attempt budget and cooldown details.
Import problems now uses readable recovery labels, an exact recovery-state filter,
and a styled **Refresh report** link that reloads the saved report.

All 51 Mylar image tests and `make validate` passed. Verified both template backups
through isolated copies before deployment, without restarting the service.
Authenticated Chromium checks verified readable labels, filtering and clearing
the filter, refresh navigation, and the new queue heading. The live queue contained
109 rows but no matching completed-import history row during this check. Completed,
retrying, and legacy states therefore used browser-only fixtures against the
deployed renderer, including the attempt tooltip. No application records were
changed by these fixtures. No page JavaScript or HTTP errors occurred. Inspected
the rendered import-page screenshot.
