# Implementation Plan: IPTV reliability and recovery

**Branch**: `codex/dispatcharr-plex-setup` | **Date**: 2026-10-19 | **Spec**: [spec.md](spec.md)

## Summary

Scope the existing Plex guide, add verified exact FAST guide matches and alternate streams, replace immediate deletion with a tested multi-day quarantine policy, configure future DVR defaults, and add scoped recurring verified backups and monitoring using the existing host and services.

## Technical Context

Python 3 standard library, native Dispatcharr Django/PostgreSQL, Plex HTTP APIs and native Plex SQLite, systemd timers, existing Restic and Prometheus/Alertmanager. No additional public listener, credentials, container privileges or paid provider. Operational configuration and receipts live outside Git. Portable helpers belong in `stacks/dispatcharr/maintenance/` with synthetic tests.

## Constitution Check

- Portable public examples: PASS, private values supplied by ignored configuration.
- Complete contracts: update affected README, preparation guidance and metadata; no changes to base ports or mandatory volumes.
- Safe operations: verified logical backups before mutation; existing media untouched.
- Security choices: host jobs explicitly scoped; no new public ingress or Docker socket inside a container.
- Generated truth: regenerate affected catalog, run focused fixtures and `make validate`.

## Research and design

See [research.md](research.md), [data-model.md](data-model.md), [contracts/maintenance.md](contracts/maintenance.md), and [quickstart.md](quickstart.md).

## Implementation order

1. Capture/restore-verify affected application state and preservation baselines.
2. Scope XMLTV while preserving Plex device/DVR/rules; improve exact EPG mappings.
3. Probe equivalent alternate sources and verify isolated failover without disrupting viewers.
4. Disable immediate plugin deletion; use dated, persistent health observations for fourteen-day/three-day quarantine admission.
5. Set future DVR defaults with commercial markers and bounded retention, preserving existing rules/media.
6. Schedule consistent backups before existing Restic, verify isolated restore, and publish bounded health signals to existing monitoring.
7. Validate portable helpers, deployed behavior, preserved data and cleanup.

## Project structure

- `stacks/dispatcharr/maintenance/`: public maintenance helpers, example configuration, timer/service examples and tests.
- `stacks/dispatcharr/README.md`: opt-in operational and recovery instructions.
- `specs/026-iptv-reliability/`: acceptance evidence and retained decisions.
- Private runtime config/state: operator-owned paths outside Git.

## Post-design gate

PASS. Existing settings remain authoritative. No image upgrade or application-wide migration is required. Exact-feed guide gaps remain explicit rather than fabricated.

## Station matrix expansion

Research current NBC/ABC/CBS/FOX public news feeds in three bounded groups using
the plan workflow's research agents. Root owns live writes. Admit only decoded
station news feeds, retain explicit missing feeds, and reuse stable standalone
channels rather than create duplicates. Reuse the installed Multiview engine
with on-demand named layouts: existing four-city, one per city, one per network.
City order is NBC, ABC, CBS, FOX. Network order follows Denver, Milwaukee, Atlanta,
Seattle, Minneapolis, Sanibel/Fort Myers. Keep the existing 720p24 software profile
unless resource evidence requires a bounded reduction; six-input network layouts
exceed the plugin's four-input recommendation and need separate acceptance.
Verify a fresh native backup before writes, all original mappings afterward,
encoded output and source motion per admitted layout, single selected audio,
resource headroom, guide labeling and recovery coverage. No new public listener.

The operator also requested PBS member stations in the same matrix. Research
regional PBS stations through the existing bounded research agents, check
geographic availability and decode before admission. PBS follows FOX in city
tile order. Add a PBS network layout only when at least two local station feeds
work. Preserve existing national and other-market PBS channels under their own
names. Do not bypass regional restrictions or persist expiring playback tokens.

The real-media checks exposed a Multiview 0.5.0 clock branch that rebases only
backward discontinuities. A large positive PTS jump enqueues future frames while
selected audio can continue. Apply the symmetric clock reset as a bounded
persistent plugin compatibility patch, with the original file covered by the
verified recovery generation. Keep the patch opt-in, version guarded and
separate from Compose preparation. Verify source syntax and actual decoded tile
output. Do not claim success from output codec headers alone.
