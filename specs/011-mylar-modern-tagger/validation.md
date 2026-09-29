# Implementation evidence

## Modern tagger UI acceptance

Verified on 2026-09-29 against the published image from PR #148,
source `0011e6457f685809dd5f4212af222a5d7aeaf8f9`. Modern remains
capability-gated and Legacy remains selected; this closes N3/T013 observability
acceptance, not global activation or the optional DDL transport.

- Authenticated production Manage, settings, Post-processing and Activity pages
  were exercised in Chromium at 390×1000 and 1920×1000, with en-US locale and
  America/Denver time zone. All six observer outcomes appeared accurately in the
  conversion table and Activity history, with original archive format retained.
- The first visual pass found compressed mobile columns. The corrected tables
  retain readable column widths inside existing horizontal-scroll regions.
  A further keyboard check found DataTables clipping its inner wrapper; removing
  that clipping restored arrow-key access from the focusable outer region.
  Final screenshots were visually inspected, including the rightmost columns.
- The readiness explanation no longer claims completed live coordination,
  canary and rollback checks are pending. Modern remains disabled in the selector;
  a forced Modern save is rejected before mutation, and reload retains Legacy.
  The live configuration file hash is unchanged by browser testing.
- A simulated HTTP 503 retains displayed results and marks them stale. Manual
  refresh restores current status. The final run observed no unexpected page,
  console, request or HTTP errors.
- Outcome fixtures came from the deployed modern publisher and native observer in
  an unprivileged, network-disabled container with no live data mounts. Added,
  updated and unchanged used the real pinned CLI; failure used a missing binary;
  timeout used a real bounded subprocess through a fixture CLI adapter;
  unsupported used the native typed failure. Pages, extras and comments survived.
  These outputs were substituted only in the test browser's status responses,
  not inserted into production history. Prior live native/NFS canary evidence
  remains separate; successful globally enabled Modern selection was not tested.
- The scoped rollout drained active work, verified the application backup through
  an isolated restore, and preserved database records and existing library files.
  NZBGet, Komga, Uptime Kuma and the normalizer retained their container identities
  and start times. The original DDL pause preference was restored and temporary
  operation backups were removed after live acceptance and preservation checks.

## Live canary and startup recovery

Scope: Mylar image from `e800ad75165737027c2faf699d8b016216840bfc`
and coordinated normalizer from `09cd7a5886585c163c3830fa107cb856c6fe81c9`,
tested on 2026-09-29. Legacy remains selected and Modern remains globally gated.

- PR #145 fixes inherited Python settings that made the modern executable import
  the vendored legacy ComicTagger package. The real-CLI regression fails in the
  prior image and passes in the fixed image. Image acceptance, repository CI,
  CodeQL, source lint and GHCR publication passed. A separate self-review covered
  subprocess callers, environment isolation and packaging without further findings.
- Quiesced application and worker backups were restored to isolated directories.
  File hashes, ownership, modes, symlinks and SQLite integrity checks passed.
  The comic library was verified in place, not copied. Only disposable canary
  copies of selected regular and annual comics were tagged.
- The published image passed manual regular/annual tagging, automatic staging and
  native placement, overwrite-disabled preservation and unsupported-preference
  rejection. Page and extra-member hashes, ZIP comments, supported attributes and
  original comic hashes survived. Modern was admitted only in the test process.
- A process was deliberately terminated after NFS source displacement. A fresh
  normalizer status confirmed it waited behind the pending tagger fence. Actual
  Mylar startup restored the original hash and cleared the fence before admission.
  This proves process-crash recovery, not power-loss or NFS-server recovery.
- An earlier verification attempt failed because root could not read an
  owner-private canary directory on the NFS mount. Automatic restoration of prior
  images and verified application state passed. The corrected test reads media as
  its owning UID without weakening directory permissions.
- After recovery completed and all pending markers cleared, the prior Mylar and
  normalizer images started with their compatible configuration and the newer
  application state retained. Both became healthy. Catalog records, downloaded
  issue/annual status and locations, SQLite integrity and the existing library
  file baseline survived. NZBGet, Komga and Uptime Kuma kept their original
  container identities and start times. The published images were then restored
  and passed the same preservation checks. This closes T014 and T023.

Modern availability remains a separate gate. The subsequent UI acceptance is
recorded above. These checks do not enable the optional DDL transport or establish
power-loss recovery.

## Startup and native caller integration

Scope: native integration against `e20d8fe`; no live service or media changes.

- `tagger_native.py` binds private recovery directories, selects v2 explicitly,
  snapshots policy and resolves annual release identity. Ambiguous/deleted identities
  fail without lookup. Backend routing remains behind the static availability gate.
- Startup reconciles publication before database maintenance or scans, including in
  Legacy mode. A subprocess killed after displacement leaves a missing filename;
  initialization restores the original before a guarded scanner can enter. Missing
  bound state or invalid receipts retains the fence and prevents admission.
- Native guards span imports, rescans, renames, moves, cover writes, web/API deletion,
  manual tagging and complete processing. Writer admission precedes the processing
  mutex, and admission failure still completes the native result queue.
- Staging receipts retain automatic output until native placement finishes. Cleanup
  only removes verified disposable copies while the unchanged original survives;
  uncertain/sole remaining copies are retained without claiming import success.
  Automatic copies retain legacy destination permission policy; manual publication
  verifies exact supported attributes. Automatic link placement is rejected before
  staging so a library link cannot point at subsequently removed temporary output.
- The durable tagger fence blocks worker recovery too. Review found the synchronous
  normalizer rescan callback would deadlock under ownership; it is now a persisted
  notification sent after release, retried without conversion. Review also found
  API deletion bypassed the web guard; the complete API path is now guarded.
- Two focused independent reviews covered preservation/state binding and native
  ownership. Corrections were rechecked. The automatic-attribute concern was
  reconciled against legacy `shutil.copy` and documented explicitly.
- Candidate builds pass the full Mylar gate and 97 normalizer tests without skips.
  The final Mylar gate also runs as UID 1000, read-only and without network/live
  mounts. It includes real pinned-CLI native manual/automatic caller fixtures,
  annual identity, canonical results, all declared source guards and patch replay.
  Repository `make ci-local`, including secret scanning, passes.

Modern remains disabled. T022 integration is complete; its old-image rollback
acceptance is retained explicitly as T023 alongside T014 live canary work. Both
images must be deployed together if normalizer coordination is enabled. Older
workers do not honor the new fence or callback sequence. This increment does not
claim live activation, old-image rollback proof, or optional DDL transport support.

## NFS publication correction

Scope: inactive, explicitly selected version-2 publisher against `4e7ca51`.

The actual NFSv4 media mount rejected version-1 atomic exchange with `EINVAL`
and exposed `system.nfs4_acl`. The new strategy preserves the displaced inode,
uses no-clobber candidate linking, and reconciles ambiguous operation results.
Bounded ACL/user-attribute manifests are applied and read back before publication;
the native handoff verifies them again. Existing exchange behavior remains default.

Eleven tests passed as UID 1000 on disposable actual-NFS archives, including the
real pinned CLI and native handoff. Cases cover six real-process crash checkpoints,
competing destinations, source replacement at displacement, RPC errors after success,
ACL-write failure, changed attributes, malformed manifests and v1 rejection without
mutation. Exact NFS ACL bytes, member bytes and file mode/ownership survive accepted
writes. All temporary media fixtures were removed; no existing comics or services
changed. Host execution passed ten cases and skipped the pinned-runtime case, which
passed in the image/NFS run. Two independent reviewers found no actionable defects;
one independently verified recovery after denied candidate linking.

The final candidate image passed 356 tests with no skips, including the unprivileged,
read-only/no-network gate. The native-package fixture was corrected to provide the
package context for the new attribute-helper import; installed helper bytes are
checked against the tested source.

This closes the publisher filesystem blocker only. Native v2 journal selection,
complete writer/scanner exclusion, startup recovery, automatic staging ownership,
annual caller identity and old-image canary/rollback remain activation gates. The
source name can be absent until recovery; Modern must remain unavailable until the
integration accounts for that interval. This is process-crash and injected RPC proof,
not evidence from a power failure or server reboot.

## Backend choice and normalizer coordination increment

Scope: additive settings and shared writer ownership against `1d8d721`.

- Metadata Tagging now includes a persisted Legacy-default backend selector. Modern
  is visibly disabled until its remaining gates close. Native config and web requests
  reject malformed, duplicate or unavailable choices before mutating settings. The
  native entry point preserves arguments and captures the chosen backend once.
- Complete native manual tagging and post-processing share a local-filesystem lock
  with opt-in worker conversion/maintenance cycles. The narrow coordination mount
  preserves the normalizer's read-only access to the rest of Mylar configuration.
- Persistent worker recovery markers span asynchronous Komga upgrades and process
  death. Busy cycles skip mutation without discarding existing errors. Missing or
  malformed state fails closed. A bound recovery-directory identity prevents lost
  or remounted jobs from being interpreted as completed recovery. Native admission
  errors still complete result queues.
- Independent review reproduced lock-file recreation admitting a second owner while
  the original inode was held. Only a newly created state directory may bootstrap a
  lock now. Existing state with a missing lock fails closed, including at startup.
  The real-process regression and reviewer reproduction pass after the correction.
- Both protocol copies are checked for equality. Real process/thread contention,
  process death, recovery fences, native completion, Compose isolation and preparation
  preservation have focused regression coverage.
- Local focused checks pass: six lock tests, seven worker-cycle tests, three native
  ownership tests and nine stack-contract tests. Repository CI and secret scanning
  pass. The settings fixture passed keyboard/form assertions and four Chromium
  viewport checks from 375 to 2560 pixels. Modern activation remains unavailable.
- Final image validation passed 345 Mylar tests and 94 normalizer tests. The
  cross-image harness verified exclusive admission, a killed-worker recovery fence
  and successful admission after reconciliation, with disposable state mounted at
  different paths in the two containers. No live service or media has changed.

- Shared processing-overlay styling now covers non-DDL DataTables without changing
  plugin-controlled visibility. An isolated Chromium fixture used both bundled
  DataTables versions with page styles loaded after the shared styles, at 375,
  768, 1440 and 2560 pixels. All eight cases verified readable colors, bounded
  centered placement and automatic dismissal after the actual plugin callback.
  The 375-pixel capture was visually inspected. This is fixture evidence, not a
  live-page or full-theme verification.

Other native rescan/file-management writers, modern producer routing, recovery cleanup,
startup admission and live rollout/canary acceptance remain pending. The worker
protocol is opt-in. This increment does not select the modern backend.

## Metadata lookup and native producer increment

Scope: inactive producer integration against `4e2f7e3`.

- ComicVine lookup validates issue, linked volume and expected volume identities,
  maps explicit provider metadata, and bounds HTTP responses and process execution.
  Private request files keep credentials out of argv and diagnostics. Redirects and
  retries are disabled. A local HTTP fixture exercises the actual worker process.
- The native-package service returns verified in-place receipts for manual work and
  disposable CBZ paths for automatic work. Automatic source bytes remain unchanged.
  Existing ComicInfo with overwrite disabled skips lookup, overrides and CLI work.
- Pending publication recovery runs before admission under a required caller-owned
  global writer coordinator. Conflicts block new jobs. Backend dispatch never falls
  back after a modern attempt. These APIs have no native settings or caller yet.
- Independent review reproduced corrupt ZIP exceptions escaping the service. The
  corrected boundary returns typed failure for both routes and preserves the source.
  Automatic failure reasons also reach the observer through the legacy fail sentinel.
- Both reviewers rechecked their areas with no remaining scoped findings. The actual
  pinned CLI passed manual and automatic service fixtures, credit/series/volume
  mapping, no-overwrite, page preservation and canonical native result checks.
- The final candidate passed 329 tests in the unprivileged, offline image gate.
  `make ci-local` passed, including the 391-commit secret scan with no findings.

Native caller/annual identity wiring, backend settings, global writer exclusion,
startup ownership, retained-staging cleanup and live canary/rollback remain pending.
No live service, setting or media was changed. Compose, preparation, environment,
ingress and stack metadata contracts remain unchanged.

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
