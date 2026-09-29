# Validation evidence

Candidate based on `97a7f524e48dcb5141df058e35576d4bf5a42fc8`, 2026-09-29.

- Focused producer, durable queue, native publication and coordination fixtures passed.
- Both candidate Docker builds passed their full isolated image gates. The Mylar gate includes native patched package import, checked source anchors, real modern CLI fixtures and the new queue integration tests. No test skips in either image build.
- `make validate` and `make ci-local` passed. The repository secret scanner found no leaks. The publication scanner checked tracked and untracked files with zero secrets or skipped files; changed files had no privacy findings.
- Two independent read-only reviews covered behavior/auth/contracts and recovery/tests/caller integration. Both identified native null rescan responses and equivalent directory spelling. Both defects were fixed with regressions, and both reviewers confirmed no remaining actionable findings. The response comment was corrected to describe JSON null.
- Real SQLite fixtures cover regular issues, annual release volume, ambiguous paths and trailing slashes. A simulated interruption after real publisher completion recovers the same token without another lookup or publication. No real power-loss test was performed.

Live reader-refresh completion and final preservation checks remain pending. Live operational receipts stay private. Isolated tests alone do not establish live behavior.

GitHub source lint caught an unused test import that local repository checks do not cover. The import was removed. No production behavior changed.

The independently configurable reader-refresh extension passed both reviewers with no actionable findings. Focused fixtures cover disabled settings, completion gating, API failure, and replay after receipt-save failure. The installed Komga OpenAPI confirms the metadata-refresh route; live resulting metadata remains to be verified.

The final source-integrity check carries the conversion hash through metadata lookup to publication. A regression replaces the archive during lookup and verifies that metadata is not published to the replacement. Both independent reviewers found no actionable issues in this delta.

PR #156 merged at `9060b97c42730926eb6ea4b66a2e300e2b75b21d`. All required checks passed for reviewed head `59ae4f4232e078f1edf69918c79f5efe8fc89df1`, with no unresolved review threads. Trusted-main publication and Pages completed successfully. The publication log records 411 Mylar tests and 109 normalizer tests passing.

Published and deployed image digests:

- Mylar: `sha256:4e4087b25bfaa4e6221631a77be710aa5244bdc804ddd97bafc58e71c297c8dd`.
- Normalizer: `sha256:39408967a8fbbada0c5e8a5a505616ef9d696b59a830c30740ee2547edf79462`.

Application-state backups passed isolated restore, file-integrity, and database-readability checks before deployment. Both services became healthy and retained the catalog and library baseline. The selected-file restore drill preserves NFS ACLs in a private manifest because the local backup filesystem cannot represent them. Restoring as the service user on the media filesystem verified those attributes, archive bytes, and permissions before any tagging.

The single-comic canary completed in one attempt and gained ComicInfo while retaining every other ZIP member, member attributes, archive comment, ownership, mode, and extended attributes. Authenticated Chromium checks passed at 390, 1024, and 1920 pixels, including Manage navigation, status refresh, existing button styling, and absence of page overflow or console/HTTP errors. Viewport captures were inspected visually. Other browser engines were not tested.

Live acceptance found that Komga's metadata-refresh endpoint alone can miss newly added ComicInfo when its cached media file list is stale. In Komga 1.27.1, `ComicInfoProvider.getComicInfo` checks `media.files`, and `TaskHandler` schedules metadata refresh after successful `BookLifecycle.analyzeAndPersist`. The optional trigger now requests reanalysis through the existing API. A regression models the stale file list. This supersedes the earlier endpoint-only assessment; corrected publication and live acceptance remain pending.

Both independent reviewers confirmed the reanalysis correction with 21 focused tests passing. Their documentation findings were corrected in the research, handoff contract, plan, and live acceptance instructions.
