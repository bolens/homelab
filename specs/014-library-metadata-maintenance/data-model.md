# Maintenance state

Existing `workflow.sqlite` stores all records.

- Policy: `library_missing_tags` and `library_nested_metadata`, strict booleans, default false.
- `library_scan/current`: traversal cursor, checked/completed timestamps and last outcome. End of traversal schedules the next sweep one hour later.
- `library_observation/<path-hash>`: exact path, file identity, enabled-policy signature, phase and bounded reason. A changed file is reinspected. Ambiguous metadata remains review-only.
- `library_repair/<source-request-hash>`: path, expected SHA-256, catalog owner, token, attempts, phase and reason. queued → repairing → completed/review. An interrupted repairing job recovers its receipt before another attempt. A publication conflict remains review-only.
- Missing tags retain the existing `converted_tag` schema and completion semantics.
