# Acceptance workflow

1. Run focused renderer, ownership, native journal, pack-binding publication/recovery, retry and reader-restoration fixtures; run both image gates and `make validate`.
2. Deploy compatible images with naming disabled using scoped restore-verified application backups. Verify health and catalog data.
3. Generate the read-only naming manifest. Check dotted names, group suffixes, annual/edition/fraction cases, reviews and collisions.
4. Enable and apply one proven entry. Verify exact archive bytes, filesystem attributes, native location/status and reader pages/readiness. Retain the existing progress safeguards; the user deferred an additional all-user reading-progress audit.
5. Verify completed DDL pack evidence across both rename and metadata publication, including overlapping references and preserved sidecars. Then apply bounded bulk batches under coordinated writer access. Changed proposals remain for review.
6. Re-run the manifest to prove idempotence; retain audit receipts and unresolved originals. Remove only completed temporary preservation copies.

The pack correction passed live acceptance in T022 at 931 completed publications, including all 13 Grimm issues and three overlapping 26/26-member records. T019/T023 bulk completion and T024 second-pass/final acceptance remain open; this canary does not establish full-library completion.

Corrective naming images have passed source/image gates and publication, but have
not been deployed during the user's pause on new privileged access. Keep the
existing bulk helpers and independent-writer hold intact. After access resumes,
use a fresh consistent backup and verified isolated restore before deploying the
corrected native parser and matching worker. Reconcile every held original
receipts under exact ownership/preservation checks; do not blindly replay rejected
naming requests. Finish the protected journal, credit-deferral and database checks
before resuming independent writers or claiming final acceptance.

Ordinary-user host/archive/reader and catalog audits are partial acceptance
evidence. A separately admitted native proposal check is operational: it holds
the shared writer guard and can reconcile pending journals. Record its ownership
and idempotence results separately, without treating them as direct database or
protected-journal verification.
