# Acceptance evidence

Date: 2026-10-22. Worktree branch: `codex/kavita-independent-services`.
Upstream source: `879b8b73eb41d66f88dde8eb874cc99a3397eb11`.

## Source and fixtures

- 127 gateway/provider/OAuth/Compose fixture tests pass.
- 14 independent-integration tests pass when the pristine pinned source export and compiled model assembly are supplied. These include actual compiled C# capability-client HTTP tests, whole-patch application and native deserialization of book, series and manga responses.
- Patched full server and Angular production builds pass.
- Ruff, Hadolint, focused YAML checks and `git diff --check` pass.
- `make validate` passes using a system-site-packages Python environment. It skips the externally generated PostHog bundle and unavailable locked Markdown lint tooling. Existing asking/harbor metadata and Stoat optional-example warnings remain. Newly added untracked files were also checked explicitly by the focused checks.
- Generated catalog and Pages output were regenerated and remained unchanged.

## Genuine provider reads

- MangaBaka production transport verified DICE metadata/three attributed ratings and Naruto editions/72 chapter records in a selected collection. The deployed gateway subsequently returned ten matches for a public test query, proving private-network outbound transport and live gateway response mapping.
- Anonymous AniList production transport verified both zero reviews and 12 public reviews for exact manga IDs. Review bodies and identities were not returned in diagnostics.
- Hardcover initially rate-limited requests, then returned HTTP 401. The copied configuration token matches the running Readarr metadata service token. Its authenticated field/series/review acceptance remains unverified. The private token was subsequently changed, but search still returned 401 and a minimal catalog lookup returned 429; no authenticated provider acceptance is claimed. The final deployed-container minimal account probe again returned HTTP 429.
- No personal provider record was modified. Fixture write mappings do not establish account acceptance.

## Images and runtime

- Updated gateway image builds, including OAuth, CBR and four exact-ID reading-list adapters. Image configuration `sha256:2e31bb4c97f78dbb4effb8e824ac01b62e6e740377e784320febeb07183adf33`. Final gateway smoke passed nonroot/read-only/authenticated HTTP, missing OAuth configuration, reserved CBR index refusal and all four exact-ID list capabilities.
- Updated native image index `sha256:44b461797f3d456a7f5416a2d540e3293f8ba9b097660dcc7beefba07f0f6646`, configuration `sha256:6aae61969e4726fd49d504010b90ce5a555224a59bd2f0b52f5553493e5b088d`. It includes browser-bound OAuth, actual token expiry/unknown PAT handling and exact-ID list matching. Disposable startup passed HTTP, config symlink/UID1000 and unauthenticated API rejection. The disposable container was removed.
- Upstream dependency advisories and compiler/asset warnings remain. Dependency remediation is not claimed.

## Library alignment

- Initial live baseline: Calibre 25 catalog books/26 formats; export 25 files; Kavita 23 series/24 chapters/24 files. The one rejected EPUB declares package version 1.0 and produces parser errors.
- Excluding Calibre recycle-bin/notes namespaces, the read-only planner finds 65 clear new EPUB works, 25 binary duplicates, one repeated candidate, three ambiguous/missing titles and 19 unsupported-format candidates.
- Stopped-state backup and isolated file restore passed for the full book tree, exports, Kavita configuration and Calibre-Web configuration. Eight SQLite databases passed integrity checks; ten distinct NFS type/mode/attribute variants roundtripped byte-exactly on NFS. Unsupported NFS ACL bytes are retained separately from Btrfs copies.
- The first isolated import detected deletion of nine expired recycle-bin files by Calibre startup cleanup. It changed no active original book files or existing catalog rows. A second rehearsal protected the recycle bin and passed every original file/record check: 65 additions produce 90 books. The live transaction subsequently passed, including explicit canonical ISBN assignment and verification, and added all 65 clear works.
- Calibre CLI configuration now uses a private temporary directory so startup warnings cannot corrupt its JSON inventory. The native preservation wrapper disables trash expiry only for the current process.
- The export helper has 22 fixture tests for mount/inventory/integrity refusal, locking, native EPUB preference, optional direct export and normalization of copies. The read-only planner has 14 tests. Direct raw export remains disabled because the user requires catalog alignment.
- The user authorized automatic registration of clear new books before the daily export. The transaction helper has 19 fixtures and the coordinator has ten. The native owner/mode/NFS rollback drill passed. A real daily cycle completed with 90 Calibre books/91 formats, 90 exported files and 90 indexed chapters/files in 88 series and 89 volumes. All 197 original source files checked unchanged, and both databases passed integrity checks.

## Outstanding completion gates

Full feature parity remains unverified. Reread/reset history remains ambiguous in the native event contract, CBR search-results access is disallowed by robots policy. Title lookup uses permitted publisher indexes with explicit partial coverage, and series review enrichment is bounded. Other provider-specific missing actions and limits are reported in the capability manifest. Configured OAuth applications and genuine intended-account action acceptance remain pending. No personal provider record was modified.

OAuth, MangaBaka sync, CBR exact-URL reads, Hardcover first-session handling and exact-ID native reading-list import are implemented with fixtures/native builds. This does not establish genuine account acceptance. That milestone used feature-family frontend gates. The account-safety addition below replaces personal controls with selected-provider/action gates.

The custom application and private gateway are live. A second stopped backup and isolated restored-state startup verified library queries and EPUB reading before recreation. Post-deployment checks verified the independent capability manifest, EPUB reading, library IDs, account identity, reading state, metadata locks and SQLite integrity before reconnecting ingress. Docker automatic address pools were exhausted, so a private /29 was selected after checking existing Docker networks and host routes for overlap. No existing network was removed. The public URL returned HTTP 200 using a browser user agent, Calibre-Web returned its expected login redirect, all four containers were healthy, and the daily sync passed again against the custom image. Installed host sources match this worktree. Task-created temporary backup and rehearsal copies were removed after verified success. Credential-dependent provider acceptance remains open.

## Account-safety addition

FR-014–018 add protected AniList/MAL removal, persistent cooldowns, selected-provider/action controls and actual native queue recovery tests. The current provider suite passes 135 tests. The independent suite passes 16 tests with all required source/assembly inputs, including 11 compiled native queue/wire cases. The original counts above describe the earlier milestone. Both hardening images build. See [hardening-review.md](hardening-review.md) for the review and final rollout evidence. Genuine personal account writes remain untested.


The hardening rollout is verified. Both volumes passed stopped-state byte/metadata restore checks and isolated candidate startup. The first attempt stopped before live replacement because a SQLite check changed auxiliary files inside a backup. The corrected attempt checked only restored copies, then passed live library/EPUB reading and native production MangaBaka search. All recorded metadata locks were compared by primary key across every table. Library identities, credentials, provider preferences, permissions and reading state were preserved. Calibre remains at 90 books/91 formats, export and native index at 90 files, and the daily timer is active. Both services retain their previous network/mount/security configuration. Operation-created backup/restore copies were removed after proof. Image identities and the review limitations are in `hardening-review.md`. Genuine personal provider writes remain untested.

## Recovery and storage follow-up

FR-019–021 cover retention after independent credentials are cleared, durable authenticated creation capabilities and bounded storage. The provider suite passes 143 tests. The independent suite passes 17 tests, including 13 compiled native queue/controller/wire cases. Fresh native processes reject changed origins, changed credentials, corrupt or oversized snapshots and revoked capabilities. Eight small-quota fixtures verify cache/receipt pressure and refusal before an external mutation. Repository validation passes with the same documented optional-tool skips. Final image and live evidence is recorded in [recovery-review.md](recovery-review.md).


The recovery/storage rollout passed stopped-state restore, SQLite integrity, isolated startup and final live preservation checks. Signed snapshots in restored and live configuration passed HMAC/origin/size and private-mode checks. All recorded metadata locks, identity/provider settings, permissions and reading state are preserved. Calibre remains 90 books/91 formats, export/index remain 90 files, and the daily timer is active. The final native queue run also asserts the disconnect notification and one mutation after reconnection. Temporary operation copies were removed after proof. See [recovery-review.md](recovery-review.md) for the final source/image checks and remaining limits.
