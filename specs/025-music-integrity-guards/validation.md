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

## Numbered groups without totals

On 2026-10-10, 84 host tests pass. Additional fixtures reject a lone later track,
duplicate positions and sequence gaps without declared totals, preserving all
input bytes and preventing publication. Contiguous prefixes, separate numbered
discs, invalid metadata and cue-based album images retain their existing behavior.
The NZBGet runtime passes the same 84 tests with one optional decoder test skipped.
Without totals, the guard cannot prove that tracks after the highest position exist.

## Metadata reconciliation and strict completeness, 2026-10-10

Implemented FR-012 through FR-014 and verified T014 through T016. Nonempty aliases
and repeated numeric fields cannot mask conflicting track/disc evidence. Declared
missing discs fail. Separate editions and unknown album folders retain boundaries
when flattening would change grouping. Strict processing retains and repairs local
playlist evidence so another pass succeeds after publication.

- Host suite: 94 tests passed, including metadata conflicts, blank fallback,
  missing discs, independent editions, repeat processing, strict coverage,
  preserved archives, cue exceptions and NZBGet/CLI option validation.
- NZBGet runtime: 94 tests ran successfully with one optional decoder fixture
  skipped by its availability guard. This skip does not establish that ffmpeg is
  absent from the installation.
- Ruff and `git diff --check` passed. `PATH=/usr/bin:$PATH make validate` passed.
  The externally generated PostHog bundle was the sole Compose rendering skip.
- Before replacing the bind-mounted script and manifest, private backup copies
  were restored to an isolated directory and verified against source hashes.
  NZBGet remained running and healthy on its existing image. Runtime tests used
  isolated fixtures. No completed media, queue records or application settings
  were changed. RequireCompleteness remains default-off.

Local evidence cannot identify an omitted tail without totals, a covering playlist
or cue-image evidence. Strict mode refuses that uncertainty. Plausible but incorrect
track totals or incomplete playlists with all their listed entries still present
cannot establish the original publisher's full release contents.


## Final playlist boundaries and independent review, 2026-10-10

FR-015 and T017 cover duplicate resolved playlist references, reconciled
obfuscated playlist aliases and release-bounded disc context. Two independent
reviewers additionally reproduced compatible repeated-tag rejection, collapsed
edition-level disc sets and unreadable rewritten playlist paths. Corrective
fixtures exercise both repeated-tag orders, differently labelled editions,
colon/backslash preservation and leading-space/comment-marker path round trips.

- Final host suite: 101 passed. NZBGet runtime: 101 ran successfully, with one
  optional decoder fixture skipped by its availability guard.
- Separate behavior/contracts and tests/failure-path reviews used frozen source
  snapshots. Reviewers verified publication-failure rollback and source-byte
  preservation in isolated fixtures. Both follow-up reviews confirmed the fixes
  with no remaining actionable findings or nits.
- The live-mounted script and manifest were backed up and restored privately to
  verify file hashes before this final update. Tests use isolated releases and
  leave completed media and application settings unchanged.
