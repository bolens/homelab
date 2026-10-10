# Implementation Plan: Music integrity guards

**Date**: 2026-10-08 | **Spec**: [spec.md](spec.md)

## Summary

Gate the NZBGet entry point before any mutation. Group bounded FLAC metadata by
album/album artist and disc number or retained disc ancestry; reject missing or
duplicate track positions when numeric totals are available. Decode recognised
audio to a null output before normalisation/publication when VerifyAudio is enabled.
Use ffmpeg with explicit audio mapping, error termination, no stdin and a timeout.

Local UTF-8 M3U-style lists are bounded to 1 MiB and local audio paths. Exact
references establish the relationship; obfuscated matching requires every
surviving same-directory FLAC to match a numbered artist/title entry in one
tagged album/disc. Missing entries stop cleanup. Complete recognised lists may
be cleaned under default settings. RequireCompleteness retains them and rewrites
local references when needed so repeat processing keeps its evidence. Unsafe,
remote and ambiguous M3U lists remain. No URL fetching or
guessed online album metadata is involved.

## Additional completeness requirements

Reconcile nonempty position aliases and slash totals before grouping. Validate
declared disc sets within album/artist and edition context. Retain directories
when flattening would merge those contexts or numbered groups without album tags.
RequireCompleteness defaults off and requires validated totals, complete local
playlist coverage or cue-image evidence for each audio file. Apply the same guard
to previews, unchanged releases and cleanup-disabled processing. Preserve source
bytes on every failure. No local sequence can establish an undeclared final count.

## Technical Context

Python 3.11 standard library on Linux; optional ffmpeg dependency. Existing
NZBGet category handling, archive limits, collision checks and recovery remain.
Tests use isolated files and archives, fault injection and generated audio.

## Constitution Check

Script, manifest and README form the affected contract. Compose, environment,
metadata, ingress and preparation interfaces are unchanged. Runtime mutation is
outside repository delivery. Rename exclusion instructions preserve existing
operator settings. No image pull, library transformation or download operation
is part of the public implementation or its acceptance gate.

## Source Ownership

- `stacks/nzbget/scripts/UnpackMusicTar/main.py`: status gate, grouping and decoder.
- `stacks/nzbget/scripts/UnpackMusicTar/test_main.py`: preservation regressions.
- `stacks/nzbget/scripts/UnpackMusicTar/manifest.json`: version and optional setting.
- `stacks/nzbget/README.md`: behaviour, limits and operator options.

## Validation

Focused unittests, Ruff, generated valid/corrupt audio, actual runtime import and
decoder availability, whitespace and `make validate`. Record optional skips and
scoped live backup/update evidence in validation.md.
