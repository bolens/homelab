# Portable homelab validation

Status: source implementation; native image and delivery acceptance pending.

## User scenarios

1. A contributor receives the same portable Linux source, stack, compiler and
   browser checks through one Woodpecker result on every PR and main push.
2. A weekly run gates internal links and reports external-link failures without
   changing their existing nonblocking policy.
3. An operator retires duplicate hosted validation only after exact native PR,
   genuine-main and cron proof, with a reversible required-check transition.

## Requirements

- Keep full Git history and the existing secret scan. Run all portable checks
  without path-filter gaps, pipeline secrets, registry credentials, host mounts,
  Docker sockets or privileged steps.
- Retain the actual .NET 10 compiler tests and Komga JDK 21 source controls.
  Missing compilers or skipped mandatory tests fail the dedicated lane. Report
  optional installed-assembly/source probes truthfully.
- Preserve the locked Playwright/Axe suite and Chrome channel. Pin public tools
  and images immutably, verify downloads and isolate per-image writable state.
- Reuse owning shared lint/Spec Kit pins and weekly link arguments. Keep external
  URL checks report-only and internal empty-input/errors fatal.
- Keep actual Docker lifecycle/publication, GitHub managed security, Pages OIDC
  and deployment evidence, metadata and updater jobs hosted.
- Default hosted retirement off behind `WOODPECKER_LINUX_CI`; require native PR,
  genuine merged-main, cron and current-head protection proof before cutover.
  No source change activates live settings or publishes an image.

## Evidence boundary

Unit/source checks establish tool, coverage and migration guards. Actual pinned
image execution, independent review, protected merge and forge/operator settings
are separate acceptance outcomes. Source-only tests do not establish cutover.
