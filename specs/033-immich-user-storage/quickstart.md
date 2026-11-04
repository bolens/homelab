# Validation guide

1. Run `python3 -m unittest discover -s scripts/tests -p test_immich_storage.py`.
   Fixtures must prove missing-setting refusal, no host-directory creation,
   preserved base services, and repeatable preparation with existing settings.
2. Run `make validate`. Report tool skips and unrelated failures accurately.
3. For an authorized live migration, follow the backup and rollback ordering in
   [plan.md](plan.md). Keep private state outside Git.
4. Verify the selected mount maps to `/data/library` and a unique probe written
   from the container appears on the expected mounted filesystem. Remove it.
5. Verify baseline records and files, enabled storage template, current account
   label and fallback behavior for future unlabelled accounts. Avoid creating
   production users or persistent test assets merely for validation.
6. Record results in [tasks.md](tasks.md), then remove operation-owned backups and
   isolated restore resources only after preservation is proved.
