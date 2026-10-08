# Validation evidence

Verified on 2026-10-08 against the implementation on
`codex/nzbget-music-integrity`. Private service state and operational recovery
records are excluded from this public acceptance evidence.

## Preservation and completeness

All 81 host unittest cases pass, including real ffmpeg-generated valid/corrupt
audio. Fixtures verify failed-status preservation, complete and partial disc
groups, duplicate numbers, cue exceptions, decoder errors and missing tools.
Missing-track and decoding failures preserve original archives and sidecars.

Local playlist fixtures cover incomplete obfuscated albums without numeric
totals, complete lists, exact multi-disc references, UTF-8 extended M3U syntax,
scene hash suffixes, featured artists, unsafe/unrelated text and cue references.
Conflicting playlists across archives fail without discarding either original
archive or hiding missing-track evidence. Unknown encodings, PLS structure,
mixed album identities and unmatched metadata remain outside M3U inference.

Empty audio fixtures cover every supported suffix, uppercase extensions,
cleanup-disabled validation and archived cue-referenced audio. Empty unknown
files remain retained. Established `.aif` extensions remain preserved.
Repeated ancillary MusicBrainz fields retain otherwise usable completeness tags.

## Sidecar recognition

CP437 fixtures cover box drawing and black-square glyphs while retaining
unknown binary/control-byte content and cue-referenced sidecars. Read-only
inspection confirmed representative scene NFOs match the cleanup predicate.

Binary SRR fixtures cover named/minimal headers, unknown content, truncation,
inconsistent lengths, unsupported flags, disguised FLAC and cue references.
A read-only hash/stat comparison confirmed the inspected SRR was unchanged.
Recognition follows the [upstream SRR format specification](https://raw.githubusercontent.com/srrDB/pyrescene/master/dev-docs/srr_spec.txt).
The check validates the bounded marker/application header, not every embedded
RAR metadata block. Sidecar-only folders retain their files.

## Runtime and repository checks

The NZBGet Python runtime runs the same regression suite with isolated temporary
fixtures. The optional real-decoder case is skipped when ffmpeg is not available
in that runtime; host availability alone does not satisfy this requirement.
VerifyAudio defaults to disabled and fails safely when its tool is unavailable.

Ruff, Markdown lint, whitespace checks and `make validate` pass. The optional
externally generated PostHog Compose bundle is skipped. Delivery additionally
requires `make ci-local`, secret scanning and checks on the PR head.

## Independent review

Two independent reviewers inspected behavior/contracts and failure/preservation
paths against base `228408da53d96533ed9d2b9c08dc7f6b11a3fd67`. The archive playlist
collision finding and adjacent `.aif` inconsistency were fixed with regression
fixtures. The stale feature-branch wording was corrected. Final review receipts
and head-specific delivery checks are recorded in the pull request.
