# Verification evidence

Date: 2026-09-24

## Repository and isolated checks

- `make validate` passed, including generated catalog and topology checks.
- The pinned Mylar image passed the startup patch and behavior gate before deployment.
- The final image gate passed all 28 Mylar tests, including four import-integrity tests and six queue-percentage tests.
- A JavaScript execution check verified table refresh at 0%, 50%, and 100% without resetting pagination.
- The pinned converter image passed 22 normalizer and maintenance tests.
- Six optional Compose override tests passed.
- Workflow syntax and `git diff --check` passed.

## Live checks completed

- Verified consistent backups through isolated restores before modifying Mylar,
  normalizer configuration and state, and Uptime Kuma.
- Verified all 609 original library archives by SHA-256 after the initial deployment.
- Preserved Mylar record IDs and existing Kuma monitor settings, notification
  settings, and assignments.
- Verified the Mylar Workers and Comic Maintenance Docker monitors were UP, each
  assigned to both existing notification routes.
- Enabled native failed-download handling and automatic replacement searches.
  Confirmed NZBGet CRC checking, automatic parity checking, repair, and unpacking.
- Quarantined seven invalid cached archives with verified copies and queued
  replacement searches through Mylar's native failure workflow.
- Corrected the unnumbered one-shot parser and observed ten imports complete.
  Submitted two uniquely matched annuals with explicit issue identifiers.
- Corrected an interrupted DDL row that obscured the active transfer. Observed
  subsequent downloads and post-processing complete. A large pack failed its
  resume attempt and switched mirrors. MEGA also reported concurrent-IP limits.

## Final live verification

- All 125 displayed queue rows had populated percentage values. Numeric sorting
  and the deployed polling patch passed endpoint checks.
- The active download advanced from 47% to 62% to 74%. Enabled workers remained up.
- All 12 matched comics were Downloaded and passed archive validation. Both
  annuals retained their original ordered page hashes.
- All 609 original library files remained present. None changed after the full
  hash audit. Mylar database integrity and original record IDs passed.
- Mylar, Komga, the maintenance worker, and Uptime Kuma were healthy. Both new
  Kuma monitors were UP with both existing notification routes. Original monitor
  and notification settings remained intact.
- Eight quarantined files and two interrupted partials passed SHA-256 verification.
  These recovery originals remain outside download and library scan roots.
- Removed the temporary backup and isolated restore copies after these checks.

## Retrospective

A running worker and a responsive progress endpoint do not prove forward progress.
Track downloaded bytes and completed imports, and exclude stale DDL records from
the active display. Resume acceptance must check both the server's byte range and
the local partial file. A provider's success response alone does not prove that an
archive or resumed transfer is complete.
