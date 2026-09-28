# Implementation evidence

## Native handoff and monitor increment

Scope: review against `6569f07`, then native result-ownership integration.

- The existing recovery implementation passed an independent review and 69 focused
  adapter/archive/metadata tests with no new actionable defect.
- Added a canonical `mylar.tagger_handoff.Published` result captured from reconciled
  receipts and verified against current source content/identity/permissions. Manual
  tagging rechecks its expected source and bypasses legacy copy/delete only on success.
- All four automatic caller expressions reject non-string results before placement.
  Legacy temporary paths and sentinel results retain their behavior. Actual native
  manual result-handling code is executed against disposable files in the tests.
- The observer now reports verified added/updated/unchanged metadata and distinct
  timeout, unsupported and conflict outcomes. Paths and raw errors stay out of results.
- Independent review reproduced a duplicate-module class identity gap. The final
  image now installs the handoff module only in Mylar's namespace; manual and
  automatic guards reject foreign/unknown typed objects. A separately loaded module
  fixture verifies this rejection. Misleading failure-retention wording was corrected.
- Eleven handoff and eight archive-monitor tests pass, including unchanged/manual,
  bulk behavior, legacy cleanup, real caller expressions and foreign class identities.
  Both reviewers verified the corrections with no remaining scoped findings.
- The final pinned image passed 314 tests in the unprivileged offline gate, including
  the real CLI result captured by the canonical native module. `make ci-local` passed
  with no secret-scan findings.

Native metadata lookup, backend settings, automatic staged output, startup admission,
writer exclusion and live UI/canary acceptance remain pending. Legacy tagging remains
selected. No live services, settings or media changed in this increment.

## Recovery gate and second seam-review increment

Scope: publisher recovery review against `52e9cc6` and an inactive startup scan API.

- Reproduced cleanup after a durable commit accepting changed permissions, a new
  source inode with identical bytes, or altered displaced bytes. Unfinished cleanup
  now revalidates source and displaced ownership/content and retains conflicts.
- Reproduced unknown states being guessed as staging failures. Receipt schema and
  state validation now precede recovery mutation. Deeply nested JSON and malformed
  paths remain unchanged and are reported as invalid journals.
- Independent compatibility review found valid pre-epoch timestamps rejected by
  the new validator and a pre-existing double-root alias bypassing pending ownership.
  Signed timestamp fields now round-trip; ambiguous roots are rejected consistently.
- Added streaming `recover_pending()` for future startup admission. It skips cleaned
  history without hashing media, reports busy token/source locks without waiting,
  releases locks before yielding, and continues valid recovery past invalid receipts.
  Tests use real crash fixtures and forbid repeating CLI work.
- Two independent reviewers verified their corrections; 30 publisher/recovery tests
  and the 301-test final unprivileged, offline image gate passed. `make ci-local`
  passed, including secret scanning. Native startup wiring and coordination with
  other writers remain pending.

The component is inactive: no settings, services or live media were changed. Compose,
environment, preparation, ingress and stack metadata contracts remain unchanged.

## Publication and seam-review increment

Scope: inactive publisher and earlier helper audit against `e48ee9e`.

- Review reproduced conflicting singleton metadata fields, discarded processing
  instructions, hardlinked staging that could reach an outside original, and final
  image omission of the tested helper files. Regression tests fail on the former
  behavior and pass after correction. Unsupported document-level XML nodes are
  rejected before writing instead of silently dropped.
- Added a private versioned journal, separate token/source locks, verified copies,
  atomic Linux exchange, and deterministic restart reconciliation. Real subprocess
  deaths before and after exchange exercise recovery without repeating the CLI.
- Independent review reproduced concurrent token reuse, historical replay blocking
  later jobs, and path aliases bypassing pending ownership. All were fixed with
  focused regressions. Retained history no longer imposes a lifetime job quota.
- Failures cover missing/changed sources, CRC errors, source growth, low space,
  exchange failure, workspace replacement, permissions, hardlinks and xattrs.
  An uncertain exchange retains both the original copy and displaced file. A failed
  child combined with a concurrent source change also retains the recovery copy.
- Final-image tests compare all five shipped helper files with tested sources and
  run the pinned CLI through verified publication, same-token replay and unchanged
  repeat tagging. Legacy runtime behavior remains covered.

The final image build and unprivileged, network-disabled candidate gate passed
292 tests. Two independent review passes closed their reproduced findings. Source
privacy scans found no secrets, privacy indicators or skipped files. `make ci-local`
passed, including the 385-commit Gitleaks history scan.

Native callers, startup scanning, other-writer coordination, actual media-filesystem
support, monitor receipts and canary/rollback evidence remain pending. The publisher
is not called by live Mylar, and no live settings or media were changed. Existing
Compose, ingress, environment, preparation and stack metadata contracts are unchanged.

## Archive reconciliation increment

Scope: inactive archive verification/reconciliation against `8713e4a`.

- Nineteen focused tests cover metadata additions and explicit replacements,
  preserved notes/extensions/bookmarks/arcs, unchanged results, member hashes,
  ZIP comments/attributes, filesystem ownership/mode, malformed names, CRC/truncation,
  input limits, source replacement and staging cleanup after output failure.
- The real CLI cases now write the reconciled XML into a new CBZ and reopen it.
  They verify exact XML and preserved non-metadata contents. Repeated tagging and
  reconciliation return unchanged without producing another output archive.
- Independent review found an out-of-buffer ZIP64 locator and NUL-truncated member
  names that could defeat the intended validation. Both were fixed with regression
  cases and re-reviewed. Additional reviewer checks confirmed cleanup preserves
  a replaced output inode and retains the source on ownership-setting failure.
- The complete build and final unprivileged, network-disabled image gate passed
  263 tests: 233 existing, 19 archive and 11 real-runtime tests. `make ci-local`
  passed. The 19 archive cases also passed independently outside the image.

This closes the in-memory-only XML verification gap. It does not implement source
publication, durable intent, crash recovery, native/manual routing or monitor
receipts. C3/C4, native, rollout and transport gates remain pending. The helper's
limits and unsupported ZIP64/split archives are documented in the stack README.
No live library files or application settings were changed for this increment.

## Runtime packaging increment

Scope: inactive modern runtime and staged-file CLI protocol against `b9e95f6`.

- Pinned ComicTagger `1.6.0b11.dev0`, 25 runtime dependencies and three build
  dependencies with artifact hashes. Built on the image's Ubuntu 22.04/Python 3.10
  runtime using ICU 70.1. Python build isolation is disabled.
- Retained installed notices and corresponding source archives for the three
  identified GPL/LGPL components. Tests compare bundled versions and hashes with
  installed distributions. Both runtime and build locks were exposed through requirements manifests. The
  first live bot runs failed to fetch their referenced `.lock` files. The corrective
  layout places the same pins and hashes directly in recognized requirements files,
  verified by successful dependency-graph run `36488315419`, which reported both
  requirement files and their packages. A subsequent version-update job remains
  unverified.
- The candidate build and final read-only, network-disabled, unprivileged image gate
  passed 232 existing tests and 11 modern-runtime tests. Real CLI writes cover
  regular issues, annuals, variants, Unicode, explicit volume 1, page/sidecar/ZIP
  comment preservation, malformed archives and missing executables.
- The installed modern CLI's version command returns exit 1 with its expected
  banner and an optional-RAR warning. The protocol accepts that exact banner and
  rejects other versions. The legacy CLI still reports ComicTagger 1.3.5.
- Independent packaging review identified source-version drift and build-lock
  discovery gaps. Both were fixed and re-reviewed without remaining findings.
  Independent CLI review found no actionable defects, but identified the limits
  below, which remain acceptance work.

The metadata reconciliation check currently inspects merged XML in memory. It does
not establish verified archive publication or full repeat-run archive identity.
T009-T014 remain pending, including native integration, crash recovery, monitor
outcomes and the live canary. Modern tagging and curl remain inactive. No live
configuration or library changes were made for this packaging increment.

The official PyPI per-version metadata reported no known advisories for the 28
distinct runtime/build pins on 2026-09-28. This does not cover native Ubuntu
packages. Only linux/amd64 has been built and tested. Arm64 remains unverified.

## Foundation increment

Scope: process and metadata foundation only, against baseline `060b782`.

- 12 real-process tests: success, exit failure, missing executable/cwd, stdin EOF,
  literal arguments, timeout, inherited pipes, output limits and secret-free repr.
- 15 XML tests: explicit volume 1/start year, paired arcs, partial/mismatched arc
  rejection, preservation, explicit overwrite policy, malformed/oversized/DTD XML.
- Independent runtime/transport-plan review: no blocking finding; clarified direct
  child reaping versus process-group termination before future real-CLI activation.
- Independent metadata/build-contract review: fixed fabricated arc pairing with
  three regressions that failed before the fix. Re-review passed all 15 tests.
- Candidate pinned-image build passed the complete 232-test Mylar gate without skips.

These results establish R1/M1/M2 helper behavior only. C1-C4, N1-N3, P1 modern-runtime,
L1 and D1-D4 remain pending. The build does not install or activate modern ComicTagger
or curl. No live configuration, library files or services were changed.

`make ci-local` passed. Publication scanning found no secrets or privacy indicators
in 107 Mylar files and 10 feature documents, with no skips. Gitleaks scanned 372
commits with no findings. PR #128 merged as `b9e95f6` and its GHCR image was
published. Subsequent capability gates remain separate.
