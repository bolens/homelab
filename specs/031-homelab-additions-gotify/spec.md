# Feature Specification: Homelab additions and Gotify migration

**Feature Branch**: Existing working branch, isolated file ownership.

**Created**: 2026-11-04

**Status**: Accepted for implementation

**Input**: Implement the six recommended additions, replace ntfy with Gotify, preserve configured notifications, and use the requested notify hostname.

## User Scenarios & Testing

### User Story 1 - Receive existing notifications in Gotify (Priority: P1)

The operator receives monitoring and image-update notifications through Gotify.

**Why this priority**: A migration must not silently lose existing alerts.

**Independent Test**: Send a message through each active producer and verify the stored Gotify message and application identity.

**Acceptance Scenarios**:

1. Given configured ntfy producers, when migrated, then each active producer delivers to Gotify with existing routing and fallback behavior preserved.
2. Given a failed delivery, when cutover verification fails, then the previous configuration and compatible services can be restored from verified private backups.
3. Given a stopped or inactive producer, when templates change, then it remains stopped or inactive.

### User Story 2 - Use the six additional applications (Priority: P2)

The operator can open Changedetection.io, Music Assistant, LubeLogger, Dawarich, HomeBox, and Wallos.

**Why this priority**: These add the household functions selected in the preceding recommendations.

**Independent Test**: Validate each standalone example, deploy, verify application health and authenticated access, and record any remaining account or device setup.

**Acceptance Scenarios**:

1. Given a new stack, when prepared twice, then existing configuration is preserved and no container starts during preparation.
2. Given a deployed stack, when opened through its intended route, then the expected application responds.

### Edge Cases

- Gotify cannot import ntfy users, tokens, subscriptions, or cached message formats directly. Preserve the old state separately and create application credentials for the new service.
- Host networking and player/provider onboarding are explicit Music Assistant requirements.
- No Home Assistant container is currently running. Do not deploy unrelated dependencies to imply an integration was completed.
- Preserve unrelated working-tree edits and never copy runtime secrets into public sources.

## Requirements

### Functional Requirements

- **FR-001**: Add seven complete stack contracts with reviewed upstream versions and persistent storage.
- **FR-002**: Migrate active Alertmanager, Uptime Kuma, and Diun notification routes, retaining the SMTP fallback.
- **FR-003**: Update stopped Watchtower settings and the inactive n8n restart approval template without activating either.
- **FR-004**: Serve Gotify at the requested notify hostname with authenticated publishing and WebSocket support.
- **FR-005**: Verify backups by isolated restore and database readability before changing persistent state.
- **FR-006**: Preserve existing records, monitor history, workflows, and ntfy data, and report any unverified client-side steps.
- **FR-007**: Regenerate catalog, topology, and site from sources and run focused checks followed by make validate.

### Key Entities

- Application: one independently deployable stack and its persistence contract.
- Notification route: producer, Gotify application, credentials, and delivery evidence.
- Migration baseline: private configuration, state copies, integrity results, and rollback instructions.

## Success Criteria

### Measurable Outcomes

- **SC-001**: All three active notification producers deliver verified messages to Gotify.
- **SC-002**: All six added applications respond through their intended routes, with onboarding gaps explicitly recorded.
- **SC-003**: Preserved database record counts and file integrity match the migration baseline outside intended changes.
- **SC-004**: Public examples contain no runtime credentials or host-specific values and repository checks pass or report exact pre-existing failures.

## Assumptions

- “gotfy” means Gotify.
- The six recommendations are all in scope. Healthchecks was explicitly deprioritized and is excluded.
- The request authorizes scoped deployment and migration. It does not authorize unrelated service upgrades or publication.
- Phone client installation, music subscriptions, and personal inventory entry require user interaction when unavailable here.

## Scope amendment: Termix

The user added Termix during implementation. Add an independent eighth stack with persistent credentials, private administrative ingress, native authentication, and no implicit host credential access. Verify login/readiness and report any SSH target onboarding still required.

## Scope amendment: dedicated OAuth model upstream

The user requested openai-oauth across services. Build a pinned upstream package, use a new private auth volume, keep its unauthenticated port reachable only by LiteLLM, and preserve existing model providers and credentials. The user performs the account login. Acceptance requires account model discovery and a successful authenticated gateway completion plus streaming, with no public upstream ingress.

The user also requested resolving LiteLLM's environment-credential login warning. Verify a regular database-backed proxy administrator before disabling the environment and master-key UI login fallback. Preserve API keys and model routes.

OAuth client onboarding adds separate restricted LiteLLM service identities to Open WebUI and LibreChat, preserving all current providers, users and conversations with verified private state backups. Client keys can access only the new personal model route.

## Scope amendment: TubeArchivist and Zimi deployment

The user explicitly authorized both applications following existing Caddy/stack conventions. Add complete portable contracts, version/digest pins, local authenticated routes, dedicated persistent storage and native application verification. TubeArchivist keeps dedicated Elasticsearch/Redis without host ports. Zimi uses bridge networking with management and library access protected. Do not start unsolicited subscriptions, downloads, automatic content updates or seeding. Preserve existing services and verify recovery before any change to their state.
