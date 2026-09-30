# Validation

Build the normalizer Dockerfile; its build stage runs the complete unittest suite with actual Poppler and archiving-utils. Check disabled configuration, mixed/rotated pages, corrupt/encrypted inputs, bounds, source mutation, collision and cache tampering.

For an isolated canary, mount only selected PDFs read-only and a fresh scratch state writable. Render all pages, compare counts/ordered hashes to the CBZ, inspect cover/interior/last page images, and confirm source hashes unchanged. Do not mount live configuration into fixture tests.

Enable `pdf_conversion.enabled` in private normalizer config after scoped backup/isolated restore. Keep existing files unchanged during preparation. Deploy only the worker with all applicable Compose overrides and `--no-deps`. Verify durable imports and current reader state before deleting operation backups.
