# Acceptance workflow

1. Run focused renderer, ownership, native journal, retry and reader-restoration fixtures; run both image gates and `make validate`.
2. Deploy compatible images with naming disabled using scoped restore-verified application backups. Verify health and catalog data.
3. Generate the read-only naming manifest. Check dotted names, group suffixes, annual/edition/fraction cases, reviews and collisions.
4. Enable and apply one proven entry. Verify exact archive bytes, filesystem attributes, native location/status and reader pages/progress.
5. Apply bounded bulk batches under coordinated writer access. Changed proposals remain for review.
6. Re-run the manifest to prove idempotence; retain audit receipts and unresolved originals. Remove only completed temporary preservation copies.
