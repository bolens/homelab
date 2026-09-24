# Validation evidence

- Twelve isolated recovery tests pass: filename and metadata identity, conflicts,
  ambiguous/downloaded issues, malformed and oversized metadata, original/copy
  hashes, restart and timeout deduplication, unsupported formats, symlink refusal,
  completed-attempt reporting, duplicate issue submissions, stale attempts, and
  native plain-text API acknowledgments.
- The pinned Mylar image passes 67 checks, including local-cache mode preservation
  through the API queue handoff. The pinned normalizer image passes 37 checks.
- Final `make validate` passed. Only the externally generated PostHog Compose bundle
  was skipped. The log is retained at `/tmp/mylar-final-validation.log`.
- Live inspection found six exact individual-CBZ candidates among 116 archives.
  ZIP packs are not automatically submitted. Both cache mounts refer to the same
  storage, and runtime recovery is enabled while portable examples default off.
- Verified consistent backups and isolated restores cover 632 Mylar files and 59
  normalizer state files, plus normalizer configuration. The library baseline has
  677 files. Final preservation checks passed and temporary backups and isolated restores were removed.
- The real import test exposed native NZBGet path remapping and plain-text response
  compatibility issues. A missing optional queue field then discarded the DDL
  flag. These are corrected and covered by regression checks. Original bytes were
  preserved throughout; unsuccessful attempts were not blindly requeued.
- End-to-end import succeeded for one uniquely matched comic.
  All 22 page hashes matched; the original source hash remained unchanged. The
  explicit native queue handoff now retains local-cache mode.
- All 677 baseline library files and 13 retained originals survived unchanged.
  Database integrity, original record IDs, unrelated settings, and both Kuma
  monitors passed. Evidence summary: `/tmp/mylar-recovery-final.json`.
- The second desktop-layout pass passed 17 loaded-page captures across widths
  1024, 1200, 1440, 2560, and 3440. Browser checks covered menu navigation,
  current-page indication, keyboard activation, Escape, outside dismissal, refresh
  styling, and status polling. No unexpected page errors or overflow remained.
  Screenshots and metrics are retained as `/tmp/mylar-wide-after-*` and
  `/tmp/mylar-wide-after.json`; the open menu is `/tmp/mylar-wide-menu-3440.png`.
