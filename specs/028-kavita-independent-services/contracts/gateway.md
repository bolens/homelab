# Gateway and adapter contract

Python modules use `metadata.Metadata(transport)` and `sync.Sync(transport, store)` objects. Implement `dispatch(path: str, payload: dict, query: dict) -> object`. Return native Kavita JSON DTO data, without the KPlusResult envelope. The gateway wraps metadata/user-info/list results as `{isSuccess: true, data: result, errorMessage: null}`. `/api/v3/Scrobble` returns native `{successful: true|false, errorMessage: ...}`. Every failure has a nonempty error message. Raise `transport.ProviderError(message, status=...)` with a fixed, credential-free message. Unsupported routes/features must raise an explicit error, never silently return empty successful data.

Transport provides `json(method, url, *, headers=None, body=None, form=None, cache_seconds=0)`, fixed HTTPS origins only, and `graphql(url, query, variables=None, token=None, cache_seconds=0)`. GraphQL returns the `data` object and raises on any errors. `transport.hardcover_token` holds optional catalog token for metadata only. Transport limits response/body size, timeouts and rate limits and redacts failures.

Store provides `confirmed(fingerprint)` and `confirm(fingerprint, response)` for successful write receipts. Account/entity serialization and request fingerprints are adapter responsibilities. Never persist access tokens or raw private payloads in receipt keys.

Request keys and responses use camelCase per Kavita JSON serialization. Provider enum: metadata Hardcover=2, MangaBaka=3, CBR=4; scrobble AniList=1, MAL=2, Hardcover=5, MangaBaka=6. OAuth enum differs and must never be inferred from scrobble enum.

Internal requests use `X-Provider-Key` and a private shared key, not an official license. No host port is published. `/healthz` is an unprivileged process check, `/capabilities` requires authentication and lists actual supported functionality. No `/api/license/*` compatibility responses are implemented.

Native functional routes: `/api/v3/Metadata/match`, `/api/v3/Metadata/series-detail`, `/api/v3/metadata/covers`; `/api/v3/Scrobble`, `/valid-access-token`, `/rate-limit`, `/want-to-read`, `/user-info`; provider health. OAuth and MAL stacks require explicit implementations or unavailable errors.

## Personal action and acknowledgment contract

Only one available provider entry with `adapters.sync.available: true` and an all-string sync capability array can authorize personal writes. Root metadata capabilities and another provider's entry grant no write. Actions include progress, want-to-read, safe removal, ratings, reviews and reading status. Friends-only reviews require their own capability. Reread/reset payloads remain unsupported.

The independent native client explicitly serializes requests using web camelCase. Native queue delivery accepts only `{successful: true, errorMessage: null}`. Missing, false, blank or malformed responses do not acknowledge an event. Transient errors and unsupported existing events remain pending. Rate-limit responses exhaust the current delivery budget.

A last-valid manifest can preserve event creation during a manifest transport outage. Delivery fetches current capabilities before contacting a personal provider. A valid manifest that removes support replaces the creation snapshot.

HTTP and GraphQL rate-limit errors persist a host cooldown in SQLite. New delays are bounded to one hour and cannot shorten existing cooldowns. GraphQL errors are never cached. Protected planning-entry deletion must verify empty auxiliary fields before writing and verify the matching entry absent afterward. A remote timeout never creates a successful receipt.

## Storage admission and recovery

`Store.reserve(fingerprint)` reserves durable protected capacity before an external write. `confirm(fingerprint, response, protected=True)` consumes the reservation only after remote confirmation. Failed/ambiguous operations leave an unconfirmed reservation. `confirmed` never treats reservations as completed receipts. Legacy and dated-progress receipts are protected from eviction. `protected=False` receipts are optional reconciliation hints and may expire or be evicted because their callers always read current remote state.

The fixed limits are 1024 metadata entries/32 MiB, 100000 combined receipt/slot entries, 1024 recent reconcilable receipts/seven days and a 512 MiB SQLite main-database budget. Full protected capacity refuses new protected operations before provider mutation. Existing confirmed retries remain readable. No automatic pruning deletes identity mappings or unclassified legacy receipts. WAL is checkpointed separately and requires normal filesystem free-space monitoring.

A native credential clear pauses independent delivery without deleting events or rule history. A private capability snapshot survives restart and is accepted only for the same origin/key with a valid HMAC and supported protocol. It authorizes creation only. A failed snapshot save adds an explicit capability limitation. The optional `KAVITA_PROVIDER_ACTIONS_FILE` path defaults beneath the application's existing config directory.
