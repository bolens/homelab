# Tasks: comic normalization

- [x] Specify supported formats, preservation, and failure behavior before implementation.
- [x] Verify upstream archive image and book-upgrade metadata and progress preservation.
- [x] Implement stable discovery, verified conversion, persistent recovery, and API refresh.
- [x] Add real archive and failure/restart regression tests.
- [x] Update all affected stack contracts and run repository validation.
- [x] Finish the existing Fathom repair and verify zero analysis errors.
- [x] Deploy automation after verified backup and prove an end-to-end conversion.
- [x] Verify original data and reading progress; remove temporary backups after success.

## Acceptance evidence

- Ten archive/state regression tests pass locally and inside the pinned converter
  image. Coverage includes CB7, CBT, compressed TAR, mislabeled CBZ, member hashes,
  collisions, unstable sources, interrupted publication, ambiguous API acceptance,
  and affected-series Mylar refresh.
- Four optional-override/preparation tests pass. `make validate`, focused Markdown
  lint for this feature, and `git diff --check` pass. Repository validation skips
  the ungenerated optional PostHog runtime bundle as expected.
- The prior five malformed Fathom archives were repaired and analyzed successfully.
  All 498 reader media records were READY, with protected records preserved.
- The isolated Komga 1.27.1 integration test passed: CB7, CBT, and CBR became
  three READY CBZ books with six pages. Native upgrade preserved reading progress,
  locked metadata, read-list membership, and the external artwork sidecar.
- The user explicitly approved writable library access and the worker deployment.
  Komga and Mylar backups passed isolated restore and integrity checks before
  deployment. The integration credential was corrected to the upstream SHA-512
  storage representation. Two live CBRs converted successfully, with retained
  original hashes and verified CBZ outputs. All 498 media records are READY.
  Protected reader IDs, all users' reading progress, read-list entries, and
  unrelated media files passed preservation checks. Mylar series/issue IDs and
  database integrity passed comparison, and the worker can access its API.
  Both containers are healthy. Temporary deployment backups were removed;
  original-archive recovery receipts remain in persistent normalizer storage.
