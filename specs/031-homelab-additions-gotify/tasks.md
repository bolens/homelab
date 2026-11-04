# Tasks: Homelab additions and Gotify migration

## Setup

- [x] T001 Record user scope and acceptance criteria in spec.md and plan.md.
- [x] T002 Inspect public contracts and privately inventory current notification producers.

## User Story 1: Notifications

- [x] T003 Add Gotify and authenticated Alertmanager conversion with meaningful delivery/refusal tests.
- [x] T004 Update all current public notification producers and n8n approval template.
- [x] T005 Back up affected live configuration/state and verify isolated restoration before cutover.
- [x] T006 Deploy Gotify, migrate active producers, preserve inactive producers, verify delivery and record preservation.
- [x] T007 Switch ingress to the requested notify hostname and verify authentication and WebSocket routing.

## User Story 2: Applications

- [x] T008 Add complete contracts for the six suggested applications.
- [x] T009 Validate idempotent preparation and explicit security/network/storage choices.
- [x] T010 Deploy and verify application routes and onboarding, recording client/provider gaps.

## Cross-cutting verification

- [x] T011 Regenerate catalog/topology/site, inspect complete generated differences, run focused validators and make validate.
- [x] T012 Record verification, remaining manual work, rollback outcome, and backup-copy cleanup.

## Dependencies and execution

T003-T004 precede T006, with T005 required before any existing-state mutation. T007 follows Gotify readiness. T008 precedes T009-T010. T011-T012 follow integrated implementation and live checks. Work is serialized to preserve the shared dirty checkout. Independent example rendering and metadata audits may execute concurrently without agents or service writes.

- [x] T013 Add Termix contract, deploy, verify application access, and document host onboarding.

- [x] T014 Install the compatible Authentik Gotify plugin and wire failed-login notifications after verified backups.
- [x] T015 Add Komodo with automation disabled and verify existing containers remain unchanged.
- [x] T016 Add a constrained Backrest snapshot browser with a read-only repository and no competing schedules or command hooks.
- [x] T017 Migrate host log collection from Promtail to Alloy after consistent backup and end-to-end log delivery proof.
- [x] T018 Assess Tube Archivist and a Docker-hosted ZIM library manager and record recommendations.

- [x] T019 Deploy a pinned openai-oauth image with a dedicated login and isolated gateway network, then verify authenticated LiteLLM access after user login.

- [x] T020 Replace LiteLLM bootstrap environment login with a verified regular admin, preserving API keys and model routes.

## Operational results and client choices

Backrest has native authentication, an enforced read-only repository, all 18 existing snapshot IDs, and a bounded restore with matching contents. The initial I/O error was confined to a stale Restic container bind mount. After verified cache backup, starting the same container refreshed that mount without changing its image, environment, schedule or snapshot IDs. No schedules or hooks were added.

Termix has a verified administrator and closed registration. SSH targets and credentials remain an operator choice. Music Assistant has a verified administrator and a read-only filesystem music provider. Actual player selection, player-specific LAN rules and playback remain manual. Dawarich's default user credentials have been replaced while preserving its user ID and location count.

Temporary operation backup/restore copies were removed after acceptance. Original ntfy and Promtail state and unrelated backup retention remain. Private receipts and operator credentials are retained outside Git. No source publication or Git delivery was performed.

- [x] T021 Add complete TubeArchivist and Zimi contracts with pinned releases, deliberate networking/resources and idempotent preparation.
- [x] T022 Deploy both with private credentials and local Caddy ingress, verify native login, anonymous denial, persistence and no unsolicited jobs.
- [x] T023 Regenerate and validate source contracts, record deployment evidence and clean up only verified operation backups.
