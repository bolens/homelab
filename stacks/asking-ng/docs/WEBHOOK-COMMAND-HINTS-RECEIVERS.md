# Poll webhook command hints — receiver guide

For signed poll integration webhooks (`event` in `vote`, `poll_updated`, `poll_deleted`), the JSON body includes `data.command_hints` with stable routing fields plus optional localization. Use this guide to branch safely across server upgrades.

## Related

- [API-REFERENCE.md](API-REFERENCE.md) — envelope, replay hardening, plan limits
- [POLL-WEBHOOK-CONTRACT-VERSIONS.md](POLL-WEBHOOK-CONTRACT-VERSIONS.md) — version string history and breaking-change log (append when default `contract_version` changes)
- [../scripts/README.md](../scripts/README.md) — `verify-poll-webhook-example.mjs`

## Contract version

Read **`data.command_hints.contract_version`** (string).

- **Current default** (when the server does not receive an override): `2026-04-webhook-command-hints-v1`
- **Override**: callers may pass `command_hints.contract_version` on the queued webhook payload for staged rollouts; receivers should still validate shape and capability flags.

**Branching rule**

1. If `contract_version` is a value you explicitly support, use your handler for that version.
2. If it is **missing** or **unknown**, treat the payload as **baseline v1**: require `poll_id`, `event`, `data.poll_path`, `data.results_path`, and `data.command_hints` with at least `chat_vote_short`, `chat_results_short`, and `hint_locale` when present; ignore unknown keys without failing.

**Capability discovery**

Prefer **`data.command_hints.capability_flags`** over guessing from `contract_version`:

- `supports_hint_packs` — `hint_packs` map is present
- `supports_contract_version` — `contract_version` is part of the contract
- `supports_hint_locale`, `supports_hint_locale_override`, `supports_supported_hint_locales` — locale behavior as documented in API reference
- `supports_streamer_context` — `data.streamer_context` is present (poll title, phase, voting pause, archived, selection mode, schedule ms); always server-sourced from the DB row at enqueue time (callers cannot spoof it)
- `supports_webhook_results_snapshot` — server supports per-target `webhook_targets[].include_results_snapshot`; when enabled for a URL, that delivery’s `data` may include `results_snapshot` (see below)
- `supports_webhook_owner_snapshot` — server supports per-target `webhook_targets[].include_owner_snapshot`; when enabled, that delivery’s `data` may include `owner_snapshot` (**sensitive** operational aggregates — see below)
- `supports_owner_events` — server supports per-target `webhook_targets[].include_owner_events`; when enabled, that delivery’s `data` may include `owner_events` (**sensitive** owner automation summaries — see below)

If a flag is `false`, do not assume the corresponding field exists; fall back to English-style defaults only if you must display something.

## Results snapshot (per webhook URL)

Set **`include_results_snapshot: true`** on an entry in **`webhook_targets`** (poll create / `PUT /poll/:id`). Only that target’s signed POSTs receive **`data.results_snapshot`**.

Shape (additive; same `contract_version` unless breaking changes are introduced later):

- `captured_at_ms`, `effective_phase`, `results_delay_applied`, `results_visible_through_ms`, `boosted_voting_enabled`
- `options[]`: each `{ option, vote_count, ... }` aligned with public poll semantics (weighted vs raw when boosted voting is on)
- `metrics`: `{ total_votes, total_weighted_votes }` — excludes quarantined ballots

If the snapshot query fails, the webhook is still delivered without `results_snapshot` for that run (check logs).

## Owner snapshot (per webhook URL — sensitive)

Set **`include_owner_snapshot: true`** on a **`webhook_targets`** entry only for URLs you fully control (same trust model as the signing **secret**: anyone with the secret can verify payloads, but this field adds **aggregate moderation-style telemetry**).

**`data.owner_snapshot`** (object), when present:

- `captured_at_ms`, `effective_phase`, `results_delay_applied` (aligned with public results delay semantics)
- `moderation_counters`: `votes_last_1m`, `unique_ip_hashes_last_1m`, `unique_accounts_last_1m`, `top_ip_votes_last_1m`, `quarantined_votes_pending`, `quarantined_votes_pending_account_linked`, `votes_account_linked_last_24h`, `votes_anonymous_last_24h`, `trust_ip_burst`, `trust_chat_burst` (same meaning as owner `GET /poll/:id` moderation counter family)
- `delayed_votes_pending`: votes not yet visible in delayed public results (non-zero when `results_delay_applied` is true)

This is **not** per-voter identity: values are counts and coarse aggregates only, but they can still aid traffic analysis. Do not enable on shared or untrusted receivers.

If the owner snapshot query fails, the webhook is still delivered without `owner_snapshot` for that run (check logs).

## Owner events (per webhook URL - sensitive)

Set **`include_owner_events: true`** on a **`webhook_targets`** entry only for URLs you fully control. This is an additive owner-automation block meant for routing, throttling, and moderation workflow hooks, not for public overlays.

**`data.owner_events`** (object), when present:

- `captured_at_ms`, `window_ms`
- `safeguard_tags[]`: current trust-stack safeguard labels from the API server
- `quarantine_recent[]`: bounded most-recent quarantined vote summaries, each `{ vote_id, reason, risk_score, created_at_ms, state }`
- `moderation_actions_recent[]`: bounded owner/API-key moderation batch summaries, each `{ action, actor_role, count, created_at_ms }`
- `truncated`: `{ quarantine_recent, moderation_actions_recent }` booleans indicating whether older rows were omitted

This field is intentionally bounded and excludes raw IPs, user ids, and other direct identity surfaces, but it is still **sensitive** operational context. Treat it like owner snapshot data and do not enable it on shared or third-party receivers you do not fully trust.

If the owner-events query fails, the webhook is still delivered without `owner_events` for that run (check logs).

## Streamer context

**`data.streamer_context`** (object) is the same on `vote`, `poll_updated`, and `poll_deleted`. Use it for chat overlays, run-of-show tools, or countdown UI without calling `GET /poll/:id` on every vote.

- `poll_title` (string), `phase` (string), `voting_paused` (boolean), `archived` (boolean), `selection_mode` (`single` | `multi`)
- `schedule_utc_ms`: `open_at`, `lock_at`, `reveal_at`, `expires_at` — each `number` (epoch ms) or `null` if unset

`expires_at` maps the poll’s expiration field. Values are normalized from DB scalars (including string bigints where applicable).

## Locale and packs

- **`hint_locale`**: active locale for the top-level `chat_*` strings (`en`, `en-gb`, `es`).
- **`supported_hint_locales`**: list the server currently ships for `hint_packs` keys.
- **`hint_packs`**: full map per locale; use this for overlays or multi-language UIs without re-parsing `chat_*` only.

Per-target delivery may set `hint_locale` via `webhook_targets[].hint_locale` (see API reference). Server default is `POLL_WEBHOOK_HINT_LOCALE`.

## Fallback behavior (recommended)

| Situation | Receiver behavior |
|---|---|
| Unknown `contract_version` | Log once, parse generically; prefer `hint_packs[hint_locale]` or `en` pack if `hint_locale` unknown |
| Missing `command_hints` | Reject or degrade: do not infer commands from `poll_id` alone in production bots |
| Partial `command_aliases` | Merge with your own defaults for missing `vote` / `results` keys if you display aliases |

## Deprecation and sunset (policy)

- **Additive changes** (new optional keys, new `capability_flags`, new locales in `hint_packs`, optional blocks such as `owner_events`) do not require a new `contract_version`; receivers should ignore unknown keys.
- **Breaking changes** (removing or renaming required fields) will ship under a **new** `contract_version` string; the previous version will remain accepted for at least one major release cycle unless security requires earlier removal (logged in [POLL-WEBHOOK-CONTRACT-VERSIONS.md](POLL-WEBHOOK-CONTRACT-VERSIONS.md) and your deploy release notes).
- Receivers should maintain a **small supported set** of `contract_version` values and a default fallback path.

## Security reminder

Always verify signature, timestamp skew, and replay id (`event_id`) before interpreting `command_hints`. See the verification example in `scripts/verify-poll-webhook-example.mjs`.
