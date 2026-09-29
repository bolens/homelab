# Validation

Run focused unittest files for conversion handoff, native tagging and normalizer notification delivery. Build both images to execute their existing offline fixture gates, then run `make validate` and `make ci-local`.

Acceptance fixtures cover exact series/annual ownership, delayed catalog update, duplicate admission, settings waits, foreign file hashes, metadata preservation, provider failure, simulated restart after publication, notification isolation and HTML escaping.

For an authorized live check, preserve and isolated-restore-check application and worker state, plus only the selected comic files. Deploy Mylar first while idle, verify health/data, then deploy the worker with `--no-deps`. Enable the private opt-in, replay selected conversion receipts, observe one verified result and reader refresh, compare all page bytes and attributes, and confirm protected-service uptime. Restore prior compatible image/state on loss or corruption. Remove only this operation's backups after proof. Do not perform a real power-loss test.
