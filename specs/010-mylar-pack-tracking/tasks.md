# Tasks and acceptance evidence

- [x] T01 Record prospective scope and inspect native annual, processing, catalog and pack status boundaries.
- [x] T02 Fix annual ID lookup and processing ownership; regress empty/error/concurrent processing and deleted annuals against native source.
- [x] T03 Prevent inferred pack-wide false status/reservation changes and unsafe reversal.
- [x] T04 Extend exact annual/edition matching and catalog missing related entries without changing existing/deleted records.
- [x] T05 Implement durable bounded pack inventory, member recovery, conversion, supplement preservation and verified duplicate cleanup.
- [x] T06 Persist and expose truthful pack/member/supplement state; distinguish resolved quarantine history.
- [x] T07 Complete realistic archive and restart/failure regression coverage and image gates.
- [x] T08 Update affected stack contracts, validate repository and review publication for secrets.
- [x] T11 Verify persistent DDL order, pause-new-starts and one-item priority with cooldown, shutdown and queue accounting fixtures and browser checks.
- [x] T09 Merge checked PR, verify GHCR publication and remote delivery.
- [x] T10 Back up/restore-test, deploy scoped idle services, verify files/records/health/uptime, clean task backup after success.

Image gates passed against the pinned native source and converter: 148 Mylar
regressions and 73 worker regressions. Independent preservation and native-contract
reviews found and verified fixes for catalog invocation, recovery interruption,
member cleanup, queue fairness, mixed containers, split-pack IDs and admission
priority. Repository `make validate` passed; `make ci-local` passed, including the full-history secret scan.
Pack automation and queue preferences were deployed from published images after
verified isolated application-state restores. Startup preservation and live
settings-loading defects were corrected through PRs 120 and 121. All baseline
comic, issue, annual and DDL IDs, downloaded status/location records, and existing
library file sizes/mtimes survived. Mylar, the changed worker and Uptime Kuma were
healthy; NZBGet and Komga retained their container identities and start times.
Only Mylar restarted for the final UI correction. Task backups were removed after
verification, with private receipts retained. The comic library was not copied.

Authenticated Chromium saved and read back all five modes while paused, verified
the Packs section, and passed layouts at 375, 768, 1440 and 2560 pixels. Phone,
desktop and Activity captures were visually inspected. A delayed-refresh check
verified stable styling on 51 controls. Pack automation is enabled and the original
queue preference and pause state were restored. GitHub, the intended mirror and
GHCR delivery were verified; completed feature branches were removed.

Live pack coverage is limited to enabled API/worker configuration and health:
no retained completed pack source was available for a fresh real transfer.
Real archive and restart fixtures provide the pack-preservation evidence.
The additional table-order/layout scope below remains open.

- [ ] T12 Add scheduler-based table sorting and compact responsive settings; verify preference changes, priority, cooldowns, pause and history ordering in fixtures and the live browser.
