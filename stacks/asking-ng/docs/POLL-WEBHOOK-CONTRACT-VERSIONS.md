# Poll webhook `command_hints.contract_version` — version log

Single source for **breaking** or **receiver-visible** changes to poll integration webhook `data.command_hints` and the default `contract_version` string. **Additive** changes (new optional keys, new locales in `hint_packs`, new `capability_flags`) stay undocumented here unless operators need a heads-up; see [WEBHOOK-COMMAND-HINTS-RECEIVERS.md](WEBHOOK-COMMAND-HINTS-RECEIVERS.md).

## Maintainer rule

When you introduce a **new** `contract_version` default in `api/src/lib/pollWebhooks.ts`, append a row below **before** or **with** the release that ships it. Link the stack or image tag in the release channel you use for deploys.

| `contract_version` | Shipped (approx.) | Breaking? | Summary |
|---|---|---|---|
| `2026-04-webhook-command-hints-v1` | 2026-04 | No (initial log entry) | Stable string for receivers; includes `capability_flags` (`supports_contract_version`, `supports_hint_packs`, `supports_streamer_context`, `supports_webhook_results_snapshot`, `supports_webhook_owner_snapshot`, `supports_owner_events`, locale flags), `hint_locale`, `supported_hint_locales`, `hint_packs` (`en`, `en-gb`, `es`), `command_aliases`, cross-event `poll_path` / `results_path` defaults, additive `data.streamer_context`, optional per-target `data.results_snapshot` (`include_results_snapshot`), optional per-target **`data.owner_snapshot`** (`include_owner_snapshot`, sensitive moderation-style counters including trust-stack burst summaries), and optional per-target **`data.owner_events`** (`include_owner_events`, bounded recent quarantine/moderation summaries plus safeguard tags for trusted owner automation). Receivers should branch on this value and use flags for optional fields. |

Additive fields under the same default `contract_version` are listed in this summary column for visibility; only **new default strings** or **documented breaking** changes require a new table row.

## Related

- [WEBHOOK-COMMAND-HINTS-RECEIVERS.md](WEBHOOK-COMMAND-HINTS-RECEIVERS.md) — negotiation, fallback, deprecation expectations
- [API-REFERENCE.md](API-REFERENCE.md) — full webhook envelope and replay rules
