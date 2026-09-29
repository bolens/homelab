# Data model

`converted_tag` records in existing workflow.sqlite use a SHA-256 key over the version, exact absolute CBZ path and conversion SHA-256. The payload path is an absolute normalized string of at most 4096 characters with no traversal, control characters or symlink ancestors. Digests are exactly 64 lowercase hexadecimal characters. Version is integer 1. API payload is at most 8192 UTF-8 bytes.

Records retain path/hash privately, filename-only display name, created/updated times, attempts, retry_at, phase, reason, optional issue/comic IDs and publication token. Attempts are bounded to 6. Catalog waits are bounded to 24 hours. Settings waits do not spend attempts. Completed/review records never run automatically again. A single serial consumer owns mutations. Publication tokens are 32 hexadecimal characters.

Phases: queued -> waiting-library / waiting-settings / tagging -> completed / retry / review. A tagging record after restart first checks its recorded publisher receipt. Clean failed attempts may retry with a new token. Uncertain publication requires review/recovery.
