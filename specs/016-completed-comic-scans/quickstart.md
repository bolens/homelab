# Validation

Run `python3 -m unittest discover -s stacks/komga/normalizer -p test_reader_scan.py` for catalog/readiness/batching fixtures. Run the complete normalizer suite in its pinned converter image, then `make validate` and `make ci-local`.

Verify initial activation reads no old archives or sends scans; five ready additions batch; one tail addition flushes on deadline; missing metadata, pending tag/conversion work, symlinks and changing files wait; restart and API failures preserve queues and pacing; library targeting and partial success retain only unacknowledged work.

For authorized deployment, use the stack's backup/restore and normalizer-only update workflow. Enable the documented config, inspect reader-scan-status.json, verify a real scoped scan acknowledgment with isolated notification state, preserve all media/app records and protected uptime, then remove only operation backups.
