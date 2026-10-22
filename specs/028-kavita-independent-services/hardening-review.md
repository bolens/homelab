# Account-safety hardening review

Date: 2026-10-22. Scope: FR-014–018 and US4 in [spec.md](spec.md).
Inspected revision: `5beb9fe17f57b99755d1a77b55e06744426729e5` plus the existing uncommitted independent-service work. Most feature files are untracked, so the review includes their contents as well as the tracked diff. This is a self-review, not an independent review.

The user requested the addition and its implementation before further account tests. The spec extension was completed during implementation. Earlier feature evidence remains in [validation.md](validation.md).

| Requirement | Source boundary | Acceptance evidence |
| --- | --- | --- |
| FR-014 | `providers/sync.py`: planning-entry read, protected-field checks, deletion, confirmation | `providers/test_sync.py`: nonempty, unknown and explicit-null fields, wrong identity/status and failed confirmation |
| FR-015 | `providers/transport.py`: shared host admission, HTTP/GraphQL errors, SQLite cooldown and cache | `providers/test_gateway.py`: restart, bounded/nonshortening deadlines, waiting request and error-cache refusal |
| FR-016 | `independent/IndependentScrobblePolicy.cs`, `independent-actions.ts`, `patch_source.py`, `IndependentProvider.cs` | `test_action_policy.py`: 33 matching native/frontend cases, plus native unsupported-action, reread/reset and outage-creation cases |
| FR-017 | Actual `ScrobblingService` and gateway, persistent native/remote fixture state | `IndependentQueueTests.cs` through `test_native_queue.py`: 11 compiled native queue/wire cases with no skips |
| FR-018 | Independent Flurl serializer, metadata match DTO, scrobble response and native acknowledgment | Native metadata/wire case and all delivery/recovery cases |

## Findings resolved

- Native Flurl used PascalCase request fields while the gateway required camelCase. The independent client now uses the web JSON serializer. The compiled test exercises metadata and queue requests through that client.
- Failure/default responses could give native events a permanent error. The independent path now retains them pending and requires explicit success without an error before acknowledgment. Native tests cover closed connections, expired tokens, blank responses, rate limits and an ambiguous remote commit.
- GraphQL errors could enter the metadata cache and rate limits did not survive restart. Errors are excluded from cache and host cooldowns persist. Admission checks the deadline again after pacing.
- Public review metadata could enable unrelated personal review controls. Frontend and native admission now use the selected provider's sync-adapter capabilities. Duplicate entries, disabled adapters and malformed capability lists fail closed.
- Temporary manifest outages could skip new local reading events. Creation retains previously learned supported actions. Delivery still requires a current manifest. The actual native creation/recovery case verifies this distinction.
- Reading-status rule controls used a progress gate. They now use the reading-status action, and unsupported unread resets are disabled. Saved provider preferences remain stored.

## Verification

- Provider suite: 135 tests pass, zero skips.
- Independent suite: 16 Python tests pass with the pinned export and compiled assemblies. This includes 11 actual native queue/wire cases and the shared C#/TypeScript policy matrix. The final repeat also passed all 16 in 55 seconds without skips.
- Both candidate Docker images build successfully from the final runtime source. No runtime source changed after that build.
- `make validate` passes. It skips the externally generated PostHog bundle and unavailable locked Markdown lint tooling. Existing Stoat optional-example and asking/harbor metadata warnings remain.
- The first isolated rollout attempt passed startup and state preservation, then stopped before live image replacement because its SQLite verifier opened the backup and changed auxiliary files. The prior services restarted. The corrected helper validates SQLite only in restored copies and leaves backup bytes unopened. A fresh stopped-state backup, isolated restore and live rollout subsequently passed.

## Assessment and limits

No remaining actionable source finding was identified in the scoped hardening after the fixes above. Incorrect account synchronization could destroy remote history, so genuine intended-account acceptance remains required even though fixture coverage passes. The pending-event policy favors retention over an unconfirmed acknowledgment. Rereads and resets remain held.

The tests use a real gateway process and compiled native service, with simulated provider APIs. They do not establish real OAuth consent, provider scopes, undocumented API behavior or genuine account-write acceptance. Hardcover field acceptance, remaining account credentials, incomplete CBR publisher coverage and other reported provider limitations still prevent a full-parity claim. Existing upstream dependency/build warnings are outside this addition.

## Live rollout evidence

- Gateway image configuration: `sha256:22f2925da00be3c5f5bf99f037983ba33fca361d786ffb16642c360bc8a70923`.
- Application image configuration: `sha256:72ad3a7498fff99ec77a114c8f7084ab4d491635c465ae87dc87956860739784`.
- Both stopped persistent volumes restored with matching file bytes, ownership, modes, timestamps and attributes. SQLite integrity passed on restored copies. The candidates ran against these copies on an isolated shared loopback network with no external connectivity.
- Authenticated capabilities, library queries and EPUB book-info, chapter and page reads passed. Anonymous library access was refused. All recorded lock fields were compared by primary key across every table, alongside library IDs/paths, identity credentials, provider settings, permissions and reading state.
- Live recreation preserved the existing mounts, networks and environment configuration. The gateway retains a read-only root filesystem, dropped capabilities and no host/public port. Public Kavita returned HTTP 200 using a browser user agent. Calibre-Web returned its expected application/login response, and Calibre-Web and Readarr remained healthy.
- Calibre has 90 books and 91 formats. All 90 exported files retained their content hashes. Kavita retained 90 indexed files. EPUB reading passed, and the native production MangaBaka search returned ten matches through the actual application client.
- The final checks confirmed that runtime source hashes match the built images and installed Calibre synchronization helpers match this worktree. The daily Calibre synchronization timer remains active. This image-only rollout changed neither Calibre nor its media files. No personal provider write was used as an acceptance test.
- Temporary backup and restore copies from both attempts were removed after successful live preservation proof. Existing backups, credentials and retention policy were preserved. Prior image tags remain available. The failed rehearsal did not replace live images, and an updated-image rollback was not required or exercised.

The remaining completion gates are T004, T008 and T026. They concern genuine provider acceptance and incomplete coverage rather than an unimplemented hardening suggestion.
