# Validation guide

1. Run Mylar processing/annual regression with pinned native source: `python3 stacks/mylar3/config/test_pack_intake.py /path/to/mylar`.
2. Run normalizer tests with the pinned archiving-utils executable; include mixed packs, repeated scans, unsafe members and wrong editions.
3. Build both image gates without live mounts. Run repository validators and strict local delivery checks.
4. Inspect authenticated pack/member state at desktop and mobile widths. Confirm readable compact buttons and no repeated-action side effects.
5. Deploy only after fresh idle checks and verified isolated backup restores. Compare databases, file hashes, settings and unrelated service uptime before deleting temporary backups.

Record actual check results in tasks.md; commands listed here are not claims of completed validation.
