# Workflow controls validation

## Candidate coverage

The implementation adds persistent activity, explicit queued DDL-to-NZB handoff,
provider-wait health, guided matching, and intake hysteresis. Optional automatic
handoff starts disabled. Existing processing and transfers can drain while new
intake waits.

- Native regression gates exercise checked patches against the pinned upstream
  application. Mylar and normalizer images build without live mounts.
- Regression coverage includes restart ownership, competing claims, uncertain
  downloader acceptance, deferred searches, authenticated POST/CSRF controls,
  changed-source rejection, explicit guided command tokens, and scoped aliases.
- A Chromium fixture uses native templates/assets and actual workflow route
  handlers with disposable state. At 1024, 1440 and 3440 CSS pixels, the page has
  no horizontal overflow and uses one or two columns as intended.
- Browser checks cover required button styling, explicit candidate selection,
  preserved unsaved settings and selection during polling, saved settings,
  repeat confirmation, and stale-response recovery. No JavaScript errors remain.
  The only HTTP failure is an intentionally injected 503 for the recovery check.
- Repository validation and the privacy scanner pass. Publication includes no
  runtime configuration, media, private source receipts, or browser credentials.

## Independent review corrections

- Capture source identity before extracting evidence, so displayed metadata and
  the confirmed file fingerprint describe the same file version.
- Provide checked release of uncertain import holds, reject delayed old command
  tokens, and preserve previous receipts during explicit reviewed resubmission.
- Transfer accepted download ownership to guided import without queuing another
  search. Active work and imported issues remain protected.

## Delivery gates

Final image rebuild, exact-commit review, required GitHub checks, publication,
verified-backup deployment and live data preservation remain pending. Their
results must be recorded before claiming delivery complete.
