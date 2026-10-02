# Validation: Music preview and recovery

Verified 2026-09-30 in isolated temporary fixtures, using the current working-tree
implementation. The acceptance contract was recorded during implementation; it
does not represent a specification that preceded the code.

- FR-001 / SC-001: Consecutive-frame recognition tests pass. Generated tagless
  MP3, ADTS AAC and AIFF files are identified, processed from misleading `.txt`
  names, preserve SHA-256 contents and decode successfully with ffmpeg.
- FR-002 / SC-002: `test_preview_lists_changes_without_modifying_release` covers
  direct and archived inputs, planned changes, unchanged bytes and modification
  times, and absence of an in-release recovery workspace.
- FR-003 / SC-005: `test_completion_summary_counts_actual_changes` and the preview
  fixture verify counts and unidentified filename reporting.
- FR-004 / SC-004: `test_unchanged_release_skips_staging_and_publication` asserts
  that scratch creation and publication are never called.
- FR-005 / SC-003: Recovery fixtures verify exact original restoration, backup
  corruption, changed output, unsafe journal, legacy journal and symlink refusal.
- FR-006 / SC-003: Fault-injected recovery write failure preserves the pre-attempt
  bytes and allows retry; an interrupted recovery resumes and restores originals.
- FR-007: Explicit command path argument tests pass; existing category and NZBGet
  success/failure tests pass.

## Gates

- 52 unittest cases passed, both focused and inside repository validation.
- Ruff passed for the script and its tests.
- `git diff --check` passed.
- `make validate` exited 0. Its generated PostHog Compose bundle was skipped
  because it is externally generated; 214 other Compose stacks rendered without
  failures. This is repository validation, not the broader CI-equivalent gate.

## Operational Limits

No live music processing, recovery command, configuration access, container
restart or deployment was performed for these additions. Legacy workspaces without
checksums require manual recovery. Other writers must be stopped before recovery;
the directory lock coordinates script instances. Recovery covers interrupted
processes and ordinary write failures; whole-machine crash durability is not
claimed.
