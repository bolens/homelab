# Validation evidence

Candidate based on `97a7f524e48dcb5141df058e35576d4bf5a42fc8`, 2026-09-29.

- Focused producer, durable queue, native publication and coordination fixtures passed.
- Both candidate Docker builds passed their full isolated image gates. The Mylar gate includes native patched package import, checked source anchors, real modern CLI fixtures and the new queue integration tests. No test skips in either image build.
- `make validate` and `make ci-local` passed. The repository secret scanner found no leaks. The publication scanner checked tracked and untracked files with zero secrets or skipped files; changed files had no privacy findings.
- Two independent read-only reviews covered behavior/auth/contracts and recovery/tests/caller integration. Both identified native null rescan responses and equivalent directory spelling. Both defects were fixed with regressions, and both reviewers confirmed no remaining actionable findings. The response comment was corrected to describe JSON null.
- Real SQLite fixtures cover regular issues, annual release volume, ambiguous paths and trailing slashes. A simulated interruption after real publisher completion recovers the same token without another lookup or publication. No real power-loss test was performed.

Remote CI, published-image identity, live deployment, and browser acceptance remain pending. The optional automated reader refresh still requires live acceptance. Live operational receipts stay private. No live behavior is claimed from isolated tests.

GitHub source lint caught an unused test import that local repository checks do not cover. The import was removed. No production behavior changed.

The independently configurable reader-refresh extension passed both reviewers with no actionable findings. Focused fixtures cover disabled settings, completion gating, API failure, and replay after receipt-save failure. The installed Komga OpenAPI confirms the metadata-refresh route; live resulting metadata remains to be verified.
