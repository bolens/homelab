# Feature Specification: Independent Kavita provider services

**Feature Branch**: `codex/kavita-independent-services`
**Created**: 2026-10-22
**Status**: Account-safety and recovery/storage hardening are verified locally and live. Genuine provider acceptance and full parity remain incomplete.
**Input**: Provide Kavita+ feature parity using self-hosted sidecars, reuse the existing Hardcover connection, and use placeholders for other credentials.

## User Scenarios & Testing

### User Story 1 - Discover and enrich library titles (Priority: P1)
Readers can match titles and fetch metadata, covers, recommendations, ratings and reviews through services they operate.
**Independent Test**: A book and a manga return provider-attributed details and covers; unavailable data is reported explicitly.
**Acceptance Scenarios**:
1. Given a configured Hardcover connection, searching a book returns matching titles and fetching one returns its available metadata, covers and reviews.
2. Given public MangaBaka data, matching a manga returns available metadata and recommendation feeds.
3. Given a failed or unsupported provider, the reader receives an explicit limitation rather than fabricated data or success.

### User Story 2 - Synchronize personal reading (Priority: P1)
Readers can connect their own provider account and send progress, reading-list changes, ratings and supported reviews.
**Independent Test**: A fixture verifies one provider event is mapped to the expected external update, while an unconfigured provider refuses with an actionable message.
**Acceptance Scenarios**:
1. Given valid provider credentials and an exact external title ID, a progress event updates the matching account and title.
2. Given missing credentials, the service performs no external write and explains which connection is missing.
3. Given ambiguous matching or a provider outage, the event remains failed/retryable instead of being acknowledged as successful.

### User Story 3 - Operate and recover the extension (Priority: P1)
An operator can build reproducible images, enable the extension explicitly, observe capabilities and return to stock Kavita while preserving library state.
**Independent Test**: Public examples render without runtime secrets, the sidecar starts in an isolated fixture, and the custom integration patch applies to its pinned upstream source.
**Acceptance Scenarios**:
1. Given the default stack, the extension remains inactive until selected.
2. Given the extension, its provider endpoint has no public or host port and authenticates application requests.
3. Before a live change, application state is backed up and restored in isolation; after deployment, data and feature behavior are checked against the baseline.

### User Story 4 - Connect accounts without losing reading events (Priority: P1)
Readers can enable supported actions for each account without exposing other account data to destructive updates. Temporary failures retain reading events until confirmed delivery.
**Independent Test**: The actual native queue sends events through an authenticated isolated gateway with persistent remote fixtures, then recovers after failures and restarts.
**Acceptance Scenarios**:
1. Given an AniList or MAL planning entry with ratings, progress, notes, tags, dates, history or custom lists, removal makes no write. Missing fields also prevent deletion. Explicitly empty optional fields permit removal only after a second read confirms absence.
2. Given HTTP or GraphQL rate limits, further calls wait for the bounded cooldown, including after gateway restart. Error responses cannot become cached successes.
3. Given public metadata support but no personal write capability, settings and new events cannot enable that write. A different provider's capabilities cannot enable it either. Saved preferences survive capability changes.
4. Given missing credentials, a closed connection, a blank response or an ambiguous remote commit, the native event remains pending with no successful acknowledgment. Recovery confirms completion with one remote mutation across gateway and native service restarts.
5. Given a temporary manifest outage after a supported action was learned, a new local reading event remains queued. Delivery waits for a fresh supported manifest.
6. Given rereads, unread resets, unsupported rules or unsupported review visibility, the operation remains held without changing remote history.
7. Given a source or image update, isolated tests and restored-state startup pass before live recreation. Library identities, all metadata lock fields, users, permissions, reading state and provider settings survive.

### Edge Cases
- Provider tokens expire or lack write scopes.
- An external title has multiple editions or conflicting IDs.
- Public API fields and rate limits change.
- A provider has no documented API or does not expose a feature.
- Retries must not duplicate reviews or reduce reading progress unexpectedly.
- Cached private account data must remain separate from public metadata.

## Requirements

### Functional Requirements
- **FR-001**: Preserve native library metadata locks, reading state, permissions and user identities.
- **FR-002**: Match the installed Kavita 0.9.1.4 provider contract and pin upstream source by commit.
- **FR-003**: Implement direct Hardcover and MangaBaka metadata/covers and all externally available recommendation, rating and review fields.
- **FR-004**: Track ComicBookRoundup coverage explicitly, including unsupported endpoints; full parity is not achieved while any requested feature is missing.
- **FR-005**: Support direct account-based sync where provider credentials and scopes permit, with explicit missing-credential errors.
- **FR-006**: Never contact the hosted Kavita+ service in independent mode or claim a paid subscription exists.
- **FR-007**: Keep provider credentials private, preserve placeholders in tracked files, and reuse Hardcover only under the user's scoped authorization.
- **FR-008**: Authenticate internal requests, enforce bounded network requests and limits, and prevent arbitrary URL fetching.
- **FR-009**: Keep existing stock deployment intact until isolated source/image checks and verified backup gates pass.
- **FR-010**: Record fixture, genuine provider, compiled-image and live acceptance separately; empty fallback results do not establish parity.
- **FR-011**: Keep Calibre as the authoritative catalog. Register clear new books before exporting to Kavita; hold ambiguous identities for review.
- **FR-012**: Automatically perform the opted-in daily registration with scoped writer coordination, verified recoverable state, an isolated rehearsal and preservation of original IDs, media and reading state.
- **FR-013**: Normalize unsupported EPUB versions in export copies only, preserving source books and preventing partial exports from replacing good output.
- **FR-014**: Refuse want-to-read deletion when remote ratings, progress, history, notes, tags or custom-list data exists or cannot be verified. Verify absence after admitted deletions.
- **FR-015**: Apply bounded shared cooldowns to HTTP and GraphQL rate limits, including after gateway restart.
- **FR-016**: Gate personal synchronization by the selected provider and action in settings, event creation and delivery. Preserve settings and hold unsupported existing events without acknowledging them. Keep rereads and resets disabled until their event semantics are supported.
- **FR-017**: Exercise the actual native queue against an isolated authenticated gateway and persistent fixture state, proving retry after unavailable gateway, ambiguous writes, token expiry and rate limits without duplicate mutations or false acknowledgments.
- **FR-018**: Preserve native request/response interoperability for metadata and personal writes. Never acknowledge an empty or malformed synchronization response.

- **FR-019**: Retain independent pending events when credentials are cleared. Reconnecting the intended account must deliver the retained event without duplication. Keep official-mode cleanup unchanged.
- **FR-020**: Restore last-valid creation eligibility after application restart during a gateway outage. Bind saved capabilities to the configured origin and shared key, reject corrupt or mismatched state, and require current capabilities for delivery.
- **FR-021**: Bound metadata cache entries/bytes and receipt admission. Preserve legacy and dated-progress retry protection. Prune only receipts for operations that reconcile remote state, and refuse a new protected write before contacting its provider when capacity is exhausted.

### Key Entities
- Provider capability: supported features, configured account and current availability.
- External title: provider identity, editions, attribution and metadata.
- Reading event: user, exact external title, event type, progress/rating/review and outcome.
- Provider connection: private token, scopes, expiry and user ownership.

## Success Criteria

### Measurable Outcomes
- All US4 failure/recovery scenarios pass through the compiled native service and isolated gateway without personal account credentials.
- A planning-entry removal fixture proves preservation for every protected field and confirms absence after a permitted deletion.
- The native and frontend action policies agree for available, unavailable, malformed and provider-mismatched manifests.
- Image rollout preserves every recorded library identity and metadata lock and every recorded user, permission, reading-state and provider-setting value.
- All requested metadata, covers, recommendation/review and sync scenarios pass for each advertised provider.
- Every unsupported capability is visible and fails without false success.
- Every external write targets the intended account and exact external title in isolated verification.
- No secret appears in tracked examples, diagnostics or test artifacts.
- The original library and reading state survive deployment and rollback verification.

## Assumptions
- The user authorizes independent sidecar images and reuse of the Readarr Hardcover API connection.
- Other credentials remain placeholders until supplied.
- Provider accounts and network connectivity are required for external data and writes.
- Feature parity is the completion target, not an assumption about undocumented provider functionality.

## Addition history

The user requested these account-safety additions before testing further integrations, then requested the spec update during implementation. FR-014–018 and US4 record that follow-up. The implementation base is `5beb9fe17f57b99755d1a77b55e06744426729e5`, with the existing uncommitted independent-service implementation retained. This addition is recorded during implementation, rather than presented as an earlier approved specification. See [hardening-review.md](hardening-review.md) for requirement-to-evidence mapping and remaining account acceptance.

## Recovery and storage addition

Requested after the account-safety review. Acceptance: clearing and restoring a token retains one native pending event and produces one confirmed mutation. A new application process restores trusted creation eligibility during a manifest outage, then delivers after recovery. Changed origins/keys and corrupt snapshots cannot authorize creation. Small-capacity fixtures prove cache eviction, protected-receipt survival, safe receipt cleanup, restart persistence and refusal before external mutation. Tests and rollout evidence are tracked under T027–030 and [recovery-review.md](recovery-review.md).
