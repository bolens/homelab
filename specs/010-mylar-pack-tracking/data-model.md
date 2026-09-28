# Data model

Pack records retain a stable source token, source digest/version, optional DDL ID, original filename, inventory completeness and ordered members. Member identity includes source-relative name and digest; category is issue, annual, supplement, sidecar or review. Import state is discovered, catalog pending, ready, submitted, review, confirmed or preserved. Submission alone is never confirmed. Confirmed records include destination/content evidence. Related supplements carry parent series identity without taking ownership of the full issue status.

Mylar stores sanitized display records in its existing workflow journal; the worker keeps private paths, checksums and extraction/import receipts in its existing state directory. Source-version changes require a new inventory, and uncertain prior submissions retain their hold. Source deletion requires every member to be preserved and fresh source/destination identity checks.
