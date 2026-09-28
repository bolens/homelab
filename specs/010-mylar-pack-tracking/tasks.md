# Tasks and acceptance evidence

- [x] T01 Record prospective scope and inspect native annual, processing, catalog and pack status boundaries.
- [x] T02 Fix annual ID lookup and processing ownership; regress empty/error/concurrent processing and deleted annuals against native source.
- [x] T03 Prevent inferred pack-wide false status/reservation changes and unsafe reversal.
- [x] T04 Extend exact annual/edition matching and catalog missing related entries without changing existing/deleted records.
- [x] T05 Implement durable bounded pack inventory, member recovery, conversion, supplement preservation and verified duplicate cleanup.
- [ ] T06 Persist and expose truthful pack/member/supplement state; distinguish resolved quarantine history.
- [x] T07 Complete realistic archive and restart/failure regression coverage and image gates.
- [x] T08 Update affected stack contracts, validate repository and review publication for secrets.
- [ ] T11 Verify persistent DDL order, pause-new-starts and one-item priority with cooldown, shutdown and queue accounting fixtures and browser checks.
- [ ] T09 Merge checked PR, verify GHCR publication and remote delivery.
- [ ] T10 Back up/restore-test, deploy scoped idle services, verify files/records/health/uptime, clean task backup after success.

Image gates passed against the pinned native source and converter: 148 Mylar
regressions and 73 worker regressions. Independent preservation and native-contract
reviews found and verified fixes for catalog invocation, recovery interruption,
member cleanup, queue fairness, mixed containers, split-pack IDs and admission
priority. Repository `make validate` passed; `make ci-local` passed, including the full-history secret scan.
Browser and live acceptance remain open. No service restart has occurred.
