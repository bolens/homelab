# Reader supplement tasks

- [x] Define factual sources, preservation rules and reader-supported scope.
- [x] Implement validated supplements and integrate future Modern tags.
- [x] Reuse journaled publication with an offline supplement mode.
- [x] Add preview/apply with private per-file restore verification and fail-stop behavior.
- [x] Verify focused enrichment/publication tests.
- [x] Complete checked image, repository gates and independent review.
- [x] Merge GitHub, verify Gitea mirror and published image.
- [x] Back up and restore-verify Mylar state; deploy only Mylar.
- [ ] Apply canary and library supplements, verify reader visibility and repeat idempotence.
- [ ] Verify catalog preservation, health and cleanup of operation-owned backups.

## Live acceptance evidence

- PR #197 merged at `1be4318c3932c256b4f50854144df7095755da65` on GitHub and Gitea. Matching image checks and the initial Mylar deployment completed after private configuration/state backups, isolated restore verification and SQLite integrity checks.
- The standalone library pass paused between publications for the user-requested combined naming and metadata pass. Its native journals prove 507 committed, cleaned publications; both writer fences are clear and its temporary per-file backup directory is empty. Retained state backups remain until final acceptance.
- The read-only remaining plan checked 2,952 eligible regular CBZs: 1,216 unchanged and 1,736 needing additions (`SeriesGroup`: 1,724; `Tags`: 1,542), with no metadata or structure errors. It excluded 27 current files with unverified repaired credits and 36 Extras. Preserve all 42 historical/current repair deferral paths and rebind them only through verified naming receipts; add newly verified repair deferrals before admission.
- Eight Halo reprint Extras received verified publisher-only `SeriesGroup` additions and remain distinct from the wanted original editions. Komga verified all eight READY with 183 total pages. Adventure Time #1 nested metadata was promoted through native publication with every non-metadata member preserved; Komga verified READY with 28 pages.
- Full-library idempotence, final catalog/database preservation, service health and operation-owned backup cleanup remain open. Mylar's post-processing health warning does not by itself prove a stalled worker: the queue was alive and empty, while retained completed intakes remained. Additional all-user reading-progress auditing was deferred by the user.
