# Reader scan contract

Optional `reader_scan` in private normalizer config: `enabled` boolean (default false), `batch_size` integer 1–100 (default 5), `max_wait_seconds` integer 1–86400 (default 300), `min_interval_seconds` integer 1–86400 (default 120). Reject booleans as numbers. Enabling requires configured `mylar.config_dir` and nonempty `writer_state`.

Uses the existing Komga API key. `GET /api/v1/libraries` supplies `id` and `root`; final file paths map only to containing library roots. `POST /api/v1/libraries/{id}/scan` requests asynchronous discovery. Accepted does not mean scan completed. Scheduled scans, conversion recovery scans and converted-book metadata refresh remain independent.

No public endpoint or environment variable is added. Config stays private; the tracked JSON example defaults disabled. Deploy only comic-normalizer with existing overrides and --no-deps. A lost response may replay a scan after durable pacing, without replaying media processing.
