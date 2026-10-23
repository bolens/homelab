# Validation evidence

## Scope

Repository implementation of Librarr v1.4.1 and opt-in reader integration,
2026-10-23. Worktree starts at `e6f9938`; unrelated local work is excluded.
The source review is a self-review, not independent verification.

## Completed checks

- Eight Librarr tests passed: missing inputs, absent media mount refusal,
  repeated preparation without data/config replacement or lifecycle calls,
  source-registry preservation, default exposure, retained torrent payloads,
  optional reader-network merge, read-only matching reader roots and existing
  audiobook/torrent compatibility.
- Real Compose CLI rendering used exact example files in disposable directories
  with a controlled environment; it did not use Docker's daemon.
- Preparation and metadata audits: zero failures; existing Stoat optional-example
  warning and missing Compose warnings for Asking/Harbor remain.
- ShellCheck and Ruff passed for the added/affected maintained source.
- Generated catalog, topology inventory, topology artifact checks and Pages
  consistency passed (218 application pages; 223 HTML files).
- Initial `make validate` rendered 215 stacks and skipped the externally generated
  PostHog bundle. Its hygiene gate caught the new timezone default; corrected
  `TZ` to portable `UTC`, then the owning hygiene audit passed.

## Final local gate

`make ci-local` passed, including all pre-commit hooks and strict repository
validation. Its full-history Gitleaks scan inspected 747 commits (about 39 MB)
and found no leaks. The separate staged publication audit inspected 45 files:
zero secrets, zero skipped files; six privacy indicators were unchanged public
example text (container home path, example LAN address and example email aliases).
The staged secret scan also passed. No second independent history scanner was
run; Gitleaks and the separate file scanner are the recorded coverage.

The only externally generated Compose bundle skipped was PostHog. Existing
native validation reported optional archive-backend controls as unproved; this
change does not alter or claim those live Mylar controls. Live network/provider checks were not run. The corrected site test was later
verified with the complete local browser suite (14 passing tests).

GitHub delivery checks and post-merge verification are recorded in the PR;
local success alone does not establish that delivery.

## Runtime boundaries

No image pull, container lifecycle action, live configuration read, provider
login, download, reader scan, Calibre import or library mutation was performed.
The image manifest/configuration was read from GHCR without pulling layers.
Its pinned release is Linux amd64; the stack does not claim native arm64 support.
The default no-host-port contract and optional network/mount boundaries are
verified from rendered Compose, not a live firewall/WAN probe.

Deployment must supply credentials, verify mounted filesystems and permissions,
back up and verify affected existing reader state, select wanted overrides,
configure exact library IDs and verify a permitted download/import. Bookshelf's
automatic direct-download fulfillment and NZBGet integration remain unsupported.

## CI compatibility correction

The first GitHub run exposed a test-only difference: the hosted Compose v2 JSON
renderer omits `create_host_path` when false; local Compose 5.6.0 includes it.
The existing optional-stack tests already handle this omission. Librarr's tests
now use that same rendered representation and independently require explicit
`create_host_path: false` in every new source bind. No mount behavior changed.
The corrected eight-test suite passed locally; the updated PR requires a fresh
GitHub check result.

The initial site-quality job also exposed a hardcoded 217-application total in
the catalog-filter browser test after the catalog grew to 218. The test now
compares the actual total and visible card counts with the displayed status,
including nonempty filtering, instead of hardcoding a fleet size.

`make site-test` passed all 14 tests after the catalog assertion correction.
