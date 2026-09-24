# Implementation plan: comic download reliability

**Date**: 2026-09-24

**Spec**: [spec.md](spec.md)

## Design and ownership

- Mylar's startup patches add an authenticated queue-health API. A container
  health probe stores observations in its config volume and detects 15-minute stalls.
- Existing Uptime Kuma read-only Docker monitoring reports health through existing notifications.
- Enable Mylar's failed-download handling and automatic replacement searches.
  Inspect NZBGet's non-secret repair settings; preserve settings already correct.
- Extend the optional Komga normalizer with completed-download maintenance.
  Its separate override mounts the completed comics directory and a separate DDL-cache directory writable.
  The remaining Mylar configuration stays read-only.
  Reuse validated archive tools, receipts, stable-file checks, and existing Mylar access.
- Quarantine retains verified source bytes outside the library. Duplicate cleanup
  requires exact ordered pages and preservation of source non-page members.
- Add an offline Mylar candidate-image gate with no network, runtime mounts, or deployment.

## Constitution check

Security changes are explicit and opt-in: a completed-download bind mount for maintenance.
Existing service ports, ingress, credentials, and read-only Docker proxy remain unchanged.
Examples contain placeholders. Preparation does not create missing media mounts or start services.

## Validation and deployment

Use real archive fixtures, worker-health state transitions, source-derived patch tests,
and candidate-image validation. Run focused contract tests and `make validate`.
Before updates, use consistent backups and isolated restore checks for Mylar, normalizer
state/configuration, and Uptime Kuma. Preserve records, original library files, monitors,
and notification assignments. Keep backups on inconclusive verification; roll back on loss.
