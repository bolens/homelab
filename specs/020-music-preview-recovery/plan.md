# Implementation Plan: Music preview and recovery

**Date**: 2026-09-30 | **Spec**: [spec.md](spec.md)

Recorded during implementation. Final evidence is in [validation.md](validation.md).

## Summary

Separate read-only planning from staged mutation. Share the plan between preview,
summary reporting and the unchanged-release shortcut. Detect AIFF and consecutive
MP3/ADTS frames from a bounded header. Add a versioned recovery record with SHA-256
checksums, preflight every restore, temporarily displace verified outputs and
verify originals before removing the workspace.

## Technical Context

Python 3.11 standard library on Linux. Runtime dependencies and NZBGet lifecycle
remain unchanged. Tests use unittest, fault injection, synthetic archives and
optional generated audio fixtures. Recovery targets process interruptions and
ordinary I/O failures; whole-machine durability is not claimed.

## Constitution Check

- Portable examples: commands use placeholder paths, no live configuration read.
- Complete contracts: script, manifest and owning README change together;
  Compose, metadata, ingress, environment and preparation interfaces are unchanged.
- Safe operations: tests run in temporary directories, no container lifecycle work.
- Runtime security choices: no mount, privilege, port or network change.
- Validation: focused tests, Ruff, whitespace and `make validate`; report skips.

## Source Ownership

- `stacks/nzbget/scripts/UnpackMusicTar/main.py`: detection, plan, CLI and recovery.
- `stacks/nzbget/scripts/UnpackMusicTar/test_main.py`: acceptance and regression fixtures.
- `stacks/nzbget/scripts/UnpackMusicTar/manifest.json`: version and capability description.
- `stacks/nzbget/README.md`: operator commands and limits.
- `scripts/validate-repo.sh`: existing regression-suite integration.

## Verification

Check each acceptance outcome in isolated fixtures, plus real generated short audio
if ffmpeg is available. Review recovery refusals, ordinary write failure rollback
and interruption resume. Finish with focused lint and repository validation.
