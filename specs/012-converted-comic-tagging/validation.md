# Validation evidence

Candidate based on `97a7f524e48dcb5141df058e35576d4bf5a42fc8`, 2026-09-29.

- Focused producer, durable queue, native publication and coordination fixtures passed.
- Both candidate Docker builds passed their full isolated image gates. The Mylar gate includes native patched package import, checked source anchors, real modern CLI fixtures and the new queue integration tests. No test skips in either image build.
- `make validate` and `make ci-local` passed. The repository secret scanner found no leaks. The publication scanner checked tracked and untracked files with zero secrets or skipped files; changed files had no privacy findings.
- Two independent read-only reviews covered behavior/auth/contracts and recovery/tests/caller integration. Both identified native null rescan responses and equivalent directory spelling. Both defects were fixed with regressions, and both reviewers confirmed no remaining actionable findings. The response comment was corrected to describe JSON null.
- Real SQLite fixtures cover regular issues, annual release volume, ambiguous paths and trailing slashes. A simulated interruption after real publisher completion recovers the same token without another lookup or publication. No real power-loss test was performed.

Live operational receipts stay private. The final live checks below supplement the isolated tests.

GitHub source lint caught an unused test import that local repository checks do not cover. The import was removed. No production behavior changed.

The independently configurable reader-refresh extension passed both reviewers with no actionable findings. Focused fixtures cover disabled settings, completion gating, API failure, and replay after receipt-save failure. The initial OpenAPI-only assessment was superseded by the live cache finding below.

The final source-integrity check carries the conversion hash through metadata lookup to publication. A regression replaces the archive during lookup and verifies that metadata is not published to the replacement. Both independent reviewers found no actionable issues in this delta.

PR #156 merged at `9060b97c42730926eb6ea4b66a2e300e2b75b21d`. All required checks passed for reviewed head `59ae4f4232e078f1edf69918c79f5efe8fc89df1`, with no unresolved review threads. Trusted-main publication and Pages completed successfully. The publication log records 411 Mylar tests and 109 normalizer tests passing.

Initial published and deployed image digests:

- Mylar: `sha256:4e4087b25bfaa4e6221631a77be710aa5244bdc804ddd97bafc58e71c297c8dd`.
- Normalizer: `sha256:39408967a8fbbada0c5e8a5a505616ef9d696b59a830c30740ee2547edf79462`.

Application-state backups passed isolated restore, file-integrity, and database-readability checks before deployment. Both services became healthy and retained the catalog and library baseline. The selected-file restore drill preserves NFS ACLs in a private manifest because the local backup filesystem cannot represent them. Restoring as the service user on the media filesystem verified those attributes, archive bytes, and permissions before any tagging.

The single-comic canary completed in one attempt and gained ComicInfo while retaining every other ZIP member, member attributes, archive comment, ownership, mode, and extended attributes. Authenticated Chromium checks passed at 390, 1024, and 1920 pixels, including Manage navigation, status refresh, existing button styling, and absence of page overflow or console/HTTP errors. Viewport captures were inspected visually. Other browser engines were not tested.

Live acceptance found that Komga's metadata-refresh endpoint alone can miss newly added ComicInfo when its cached media file list is stale. In Komga 1.27.1, `ComicInfoProvider.getComicInfo` checks `media.files`, and `TaskHandler` schedules metadata refresh after successful `BookLifecycle.analyzeAndPersist`. The optional trigger now requests reanalysis through the existing API. A regression models the stale file list. This supersedes the earlier endpoint-only assessment; corrected publication and live acceptance passed as recorded below.

Both independent reviewers confirmed the reanalysis correction with 21 focused tests passing. Their documentation findings were corrected in the research, handoff contract, plan, and live acceptance instructions.

PR #157 merged the reviewed correction at `f6c0a4f15a80528fcb661c2b91ae48f056eef5bd`. Required checks and trusted-main publication passed. The final normalizer image is `sha256:62ea950d9647e7ef22d79d906ed075cb9fcd5899babda1dba0d55bbe8482cb82`; Mylar retains the digest above. A fresh verified normalizer-state backup protected the second update, which did not restart Mylar.

All 18 selected converted comics completed tagging in one attempt each. Replaying reader notifications did not repeat tagging. Automatic reanalysis imported the resulting metadata for all 18 books, including the three missed by metadata refresh alone. ComicInfo title, summary, and number were compared with the reader where applicable and unlocked. Reader page counts and returned reading progress remained unchanged. Both independent configuration options were enabled privately; public defaults remain false.

Final verification retained 2,038 series, 12,549 issues, 120 annuals, and 373 DDL records. Existing library files remained unchanged except the selected ComicInfo additions; every selected archive retained its other content and attributes. Mylar settings were unchanged, and worker settings changed only by the two authorized options and image pin. Mylar, the normalizer, Komga, NZBGet, and Uptime Kuma were healthy. Komga, NZBGet, and Uptime Kuma retained their container identities and start times. The original DDL pause policy was restored. Only this operation's backup and restore copies were removed after successful verification; no full-library backup or real power-loss test was performed.
