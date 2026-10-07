# Validation workflow

1. Run `python3 -m unittest discover -s stacks/mylar3/config -p 'test_publication_guard.py'` and the worker’s equivalent focused suite. Verify matching independent payload vectors, registry census/restart controls and allowed/different/conflicting owner cases.
2. Exercise actual patched native ordinary/annual/storyarc/oneoff paths with metadata enabled, disabled and Legacy selected. Assert the guard precedes scripts/tagging/placement/status writes and retained-review does not trigger failure/search replay.
3. Run affected native rescan/tagging/naming/recovery/supplement and converter-backed worker import/pack/conversion/naming fixtures. Verify no submit, false confirmation or cleanup on conflict or unavailable evidence.
   Run the owning `test_publication_lineage.py`, `test_publication_derivative.py`,
   `test_reviewed_derivative.py`, `test_publication_reconcile.py` and
   `test_combined_cleanup.py` controls. Independently run the worker's
   `test_publication_derivative_vectors.py` with literal proof vectors and actual
   old/new archives, catalog drift and inherited wrong-owner checks. Full reviewed
   census contents must match the immutable registration predecessor.
4. Run `make ci-local`; require complete actual native and worker image gates on the reviewed PR head. Verify publication against the merged revision.
5. When privileged access is permitted, coordinate all writers, take a scoped consistent backup and independently verify isolated restores. Deploy the matching native image held/uninitialized first, then authenticate and prepare/commit the exact reviewed epoch/bootstrap intent under writer exclusion with its verified backup attestation. Verify native data and protocol before deploying the matching held worker and admitting one exact reviewed correction. Uninitialized application status/bootstrap remains available while media mutations and pending replay stay held.
6. Prove a retained known-payload conflict and a legitimate different payload. Reconcile exact existing wrong copies outside scanned libraries while preserving correct bytes/owners/readers and legitimate acquisition intent. Verify databases and fresh complete library scope before resuming workers or removing only accepted temporary copies.

The reviewed native V6 and held worker V7 images are selected. Consistent backup and independent restore, exact catalog preservation, authenticated bootstrap and all 13 reviewed correction-family registrations have passed. Actual advisory canaries pass against the complete revision-13 census. Complete current-library verification, archive recovery, DDL reconciliation, live processing/restart acceptance and final cleanup remain incomplete. Keep Mylar startup-held and the worker Created until those operational gates pass; advisory decisions and image tests alone do not release either hold.

## Exact retained-repeat sequence

1. Keep writers held and complete the scoped backup and independent restore checks.
   Review private scope and correction JSON against the input contract, including
   every current correct owner, exact wrong copy and complete current census.
2. Run the read-only planner with `--scope-file`, `--review-file` and `--output`
   through `scripts/prepare-publication-corrections.py`. Use private owned inputs
   and an existing mode-0700 output directory. Review the mode-0600 output; its
   `executable=false` value never authorizes a mutation.
3. For an ordinary same-payload registration, authenticate `publicationControl`
   with the primary key, POST `prepare-registration` using the exact generated
   request, then explicitly accept the returned native token through the documented
   registration protocol. Already registered mixed derivative families require
   their existing exact family relation; the planner's single inventory is an
   anchor, not permission to flatten variants into a new version-1 registration.
4. Prepare a fresh private plan after registration. POST `commitRetainedRepeat`
   with only `request`, containing the exact version, current plan path/digest,
   manifest/independent-restore receipt paths/digests, current census and
   `repair=retain-and-clear-exact-false-location`. Native acceptance must freshly
   prove every correct family owner and the registered wrong copy. An uncertain
   attempt stays held for explicit review.
5. Query `retainedRepeatStatus` with only the returned token. Verify private
   retention, false-location removal, unchanged correct files/owners and database
   integrity. Its `requires_review=true` outcome preserves status and wanted intent;
   resolving false Downloaded status needs separate actual acquisition history or
   explicit reviewed policy. Complete the reader, canary and whole-library checks
   before releasing holds or removing accepted temporary copies.
