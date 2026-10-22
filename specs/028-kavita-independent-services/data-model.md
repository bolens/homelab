# Data model

- Public metadata cache: provider, normalized route/request fingerprint, payload, expiry. Never store tokens in keys or payloads.
- Confirmed sync receipt: fingerprint of provider/account/title/event payload and timestamp, confirmed response, created time. Persist only confirmed completion. Serialize per account/title to prevent concurrent conflicting writes. Unknown timeout outcomes remain errors until verified remotely.
- Provider credential: gateway catalog token or per-user Kavita token. Catalog token is never a fallback for personal writes.
- Capability manifest: protocol version, independent mode, provider feature support/configuration and explicit limitations. Credential presence is not proof of scope or remote health.
- OAuth transaction, when implemented: random state, expiry, fixed callback, opaque Kavita callback identity and PKCE verifier; single-use consumption.

## Account-safety addition

- Provider cooldown: fixed upstream host and wall-clock deadline in `cooldowns`. Persist across gateway restart, cap new waits at one hour, and retain the later existing deadline. This table contains no token or account payload.
- Personal action snapshot: the last valid manifest's sync-adapter capabilities, indexed by provider. Transport failure retains the creation snapshot. Valid removal replaces it. Delivery still requires fresh availability. Public metadata capabilities cannot grant a personal action.
- Native queue state: an unconfirmed event remains pending without a permanent error. Only explicit confirmed success permits processing. The gateway's durable receipt records confirmed completion and prevents a retry from repeating a confirmed mutation.
- Removal precondition: preserve remote progress, rating, history and auxiliary fields. Unknown fields fail the precondition. Verification after deletion must show the same account/title entry absent before recording completion.

## Recovery and storage state

The application stores `independent-actions.json` in its existing configuration volume. A bounded envelope carries the gateway origin and capability manifest with an HMAC using the private shared key. No key or provider credential appears in the file. Only creation admission may use restored state. Fresh delivery gates remain unchanged. A valid manifest replaces saved state, including removal of support.

`receipt_slots` reserves one protected fingerprint before an external progress write. An ambiguous operation keeps its slot across restart. Confirmation moves the slot to `receipts`. Legacy receipts have no eviction classification and remain protected. `receipt_retention` classifies only new receipts for remotely reconciled operations, with a seven-day expiry. Protected receipts and unknown reservations never expire automatically. Capacity refusal retains the native event for operator review. Stable `external_ids` are never recycled.

Cache limits are 1024 entries and 32 MiB of serialized UTF-8 payload. Receipt/slot admission allows 100000 combined protected or recent entries. At most 1024 recent reconcilable receipts survive, with pressure eviction allowed. The SQLite main database has a 512 MiB page budget. WAL autocheckpointing and a 16 MiB retained-journal target limit routine growth, but these settings are not a filesystem quota and active-reader WAL growth remains possible.
