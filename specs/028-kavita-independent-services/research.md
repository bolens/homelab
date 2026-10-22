# Research decisions

All Kavita contracts were inspected using `git show v0.9.1.4` from upstream commit `879b8b73eb41d66f88dde8eb874cc99a3397eb11`. The current upstream checkout is newer and is not accepted as pinned-version evidence.

- Use a private provider gateway because metadata, covers and scrobbling currently call `https://plus.kavitareader.com` with license headers. A local boolean cannot reproduce hosted data.
- Keep paid license state separate from independent feature availability. The fork needs explicit mode and authenticated endpoint, functional frontend/backend gates, scheduling, and subscription-job separation.
- Preserve LinuxServer runtime behavior using its installed immutable image as a base; upstream packaging uses a different config/UID contract.
- Hardcover metadata uses an existing user-authorized Readarr token. Reuse it privately; do not infer that a catalog token grants account-write permission or authorizes a write to the Readarr account for all Kavita users.
- MangaBaka metadata is publicly available; authenticated library operations require separate configured accounts and verified schemas.
- AniList/MAL provide documented direct APIs. Missing credentials disable writes; pending or failed writes never produce successful acknowledgements.
- ComicBookRoundup has no verified documented API. Review parity remains an explicit gap until a tested connector exists.
- The v0.9.1.4 tag declares AssemblyVersion 0.9.1.3. Bind the custom build to source SHA and patch identity and verify API compatibility before rollout.

Official references: [Kavita source](https://github.com/Kareadita/Kavita/tree/879b8b73eb41d66f88dde8eb874cc99a3397eb11), [MangaBaka API](https://mangabaka.org/data/api), [Hardcover API](https://api.hardcover.app/), [Hardcover documentation source](https://github.com/hardcoverapp/hardcover-docs), [AniList authentication](https://docs.anilist.co/guide/auth/), [MAL API](https://myanimelist.net/apiconfig/references/api/v2).

## Account-safety decisions

The MAL official reference exposes PATCH and DELETE for `/manga/{manga_id}/my_list_status`. Its operation name is not evidence of the HTTP method. The documented list-status fields include comments, tags, dates, priority and reread history. Removal requests explicitly fetch these fields. AniList removal deletes an entire list entry, so it also requires empty scores, progress, repeat, notes, dates, custom lists and advanced scores. Missing fields fail closed. Explicit null optional containers are distinguishable from missing fields.

Use persistent host cooldowns for GraphQL rate errors because HTTP 200 alone does not establish successful execution. Never cache a GraphQL error. Recheck the deadline after request pacing so another thread's rate-limit response can stop an already waiting request.

Compiled native tests exposed a camelCase mismatch that adapter-only tests missed. Configure the independent Flurl client with the web JSON serializer and verify both metadata and queue calls through the actual client. Blank scrobble responses remain unconfirmed.

Retain creation eligibility from the last valid manifest during transport failures so new local events survive an outage. Require current capabilities for delivery. This preserves pending events without treating stale capabilities as permission for a remote write. Exact provider-ID matching, existing library permissions and official-mode behavior remain in place.

Evidence of genuine account behavior remains separate from fixture behavior. Reread/reset semantics, incomplete CBR coverage and unconfigured provider accounts are unresolved parity limits.

## Recovery follow-up decisions

Tracing credential removal found two deletion paths: `CleanupOldOrBuggedEvents` and the controller's explicit provider-event purge. Both now preserve independent pending events. Official mode retains its existing cleanup. Credential clearing handles the empty-token provider-info branch inline, preserving its UI update notification without provider HTTP or background work.

A persisted, authenticated last-valid capability snapshot supports event creation after a cold restart during an outage. It cannot authorize delivery. Bind it to both origin and key, atomically replace a mode-0600 file, reject oversized/corrupt snapshots, and persist valid capability revocation.

A time-only expiry for progress receipts can allow duplicate replay after a long outage. Preserve protected/legacy receipts and ambiguous reservations instead. Bound admission and pause at capacity. Only receipts whose adapters already reconcile current remote values may be pruned. Keep stable external identity mappings intact. A physical SQLite page budget supplements cache/row budgets, with WAL behavior documented separately.
