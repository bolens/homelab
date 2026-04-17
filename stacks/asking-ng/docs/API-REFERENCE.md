# asking-ng API reference (operator view) 🧩

## Purpose

Operator-focused API summary for common routes, auth rules, error patterns, and optional integrations.

## Use This When

- You need a route family map without digging through code.
- You are validating auth/error behavior during deploys or incident response.
- You want quick integration guardrails for webhooks or LLM gateway setup.

## Related Docs

- [../README.md](../README.md)
- [CI-REPO-WORKFLOW.md](CI-REPO-WORKFLOW.md)
- [OPERATIONS.md](OPERATIONS.md)
- [MONETIZATION-AND-PACKAGING.md](MONETIZATION-AND-PACKAGING.md)
- [POLAR-BILLING.md](POLAR-BILLING.md)
- [OSS-AND-COMMERCIAL-POSITIONING.md](OSS-AND-COMMERCIAL-POSITIONING.md)
- [../scripts/README.md](../scripts/README.md)
- [WEBHOOK-COMMAND-HINTS-RECEIVERS.md](WEBHOOK-COMMAND-HINTS-RECEIVERS.md) — `command_hints.contract_version`, locale packs, receiver fallback and deprecation policy
- [POLL-WEBHOOK-CONTRACT-VERSIONS.md](POLL-WEBHOOK-CONTRACT-VERSIONS.md) — default `contract_version` history / breaking-change log for receivers

For migration status and refactor phases, check the current repo migration docs and tracker notes.

## At-a-Glance Endpoint Map

| Goal | Primary endpoints | Notes |
|---|---|---|
| Service health | `GET /healthcheck`, `GET /ready`, `GET /info`, `GET /status/history` | `/ready` validates DB connectivity; in `INCIDENT_MODE`, `/status/history` serves a static degraded fallback if DB history query fails |
| Session billing links | `GET /profile/billing` | JWT session; returns Polar portal/checkout URLs from `POLAR_*` when configured; includes **`usage.usageLedger`** (recent customer-visible metered rows, latest first; currently `usage.data_export`, `usage.campaign_attribution_shed`, `usage.poll_webhook_delivery_shed`, `usage.ws_fanout_shed`, and `usage.api_rate_limited` from `audit_logs`), **`usage.usageLedgerDaily`** (UTC-day grouped rollups for the same action taxonomy, default trailing 14 days), and **`usage.usageReconcile`** (internal meter-vs-raw check summary; UTC-day checks for `data_exports`, shed telemetry parity for `campaign_attribution` / `poll_webhook_delivery` / `ws_fanout`, plus `api_rate_limit` parity). For `selfhost-pro`, `billing.selfhostProLicense` now exposes phase-1 license status (`active` / `grace` / `expired` / `unknown`) from env-backed timestamps. With **`BILLING_ENFORCE_LIMITS`**, usage meters are also returned (polls, votes, exports, WS caps, optional UTC-minute **poll webhook** delivery counter + **`warnings`**). Current product priority: use this endpoint as the source for a customer-facing billing hub in `Settings`. |
| Poll creation and reads | `POST /poll`, `GET /poll/:id`, `GET /poll/:id/meta`, `GET /poll/:id/export`, `POST /poll/:id/embed-read-url`, `GET /s/:slug` | Supports phase schedule, boosted voting, vanity slug, embed gates, per-poll `theme_preset`, optional `selection_mode` (`single` / `multi`), optional retention policy (`retention_ttl_days` / `auto_delete_at_ms`), and UTM impression attribution |
| Owner updates | `PUT /poll/:id`, `DELETE /poll/:id`, `POST /poll/:id/clone` | Auth via poll `api_key` or owner JWT; draft polls can grant collaborator edits via `shared_editor_user_ids` |
| Voting and realtime | `PUT /poll/:id/vote`, `GET /ws/poll/:id` | Includes anti-abuse controls and websocket refetch model |
| Moderation and audit | `GET /poll/:id/quarantine`, `PUT /poll/:id/quarantine/:voteId`, `PUT /poll/:id/moderation/batch`, `GET /admin/audit-logs` | Quarantined votes stay out of public totals until approved |
| Optional integrations | `GET /api-docs`, `POST /platform/webhooks/:provider`, `/llm/*` | Feature-gated with env flags; `INCIDENT_MODE` disables LLM and suppresses outbound webhook deliveries |
| Billing downgrade simulation (admin) | `POST /admin/billing/downgrade-simulate` | Admin/elevated auth; dry-run check for a target plan and owner user: evaluates active polls, current UTC-month votes, current UTC-day exports, plus premium feature presence (`webhook_targets`, custom retention) and returns predicted `USAGE_LIMIT_*` / `PLAN_LIMIT_*` violations before an actual plan change |

## Response and Error Model

| Topic | Behavior |
|---|---|
| Error envelope | `{"error":{"code":"<UPPER_SNAKE>","message":"<human>","details"?:...},"requestId":"<uuid>"}` |
| Success shape | Poll routes keep legacy success wrapper `{"status":"success","data":...}` where already established |
| Rate limits | `429` with codes like `RATE_LIMIT_AUTH`, `RATE_LIMIT_ADMIN`, `RATE_LIMIT_CREATE_POLL`, `RATE_LIMIT_VOTE`, `RATE_LIMIT_LLM` |
| Readiness failure | `GET /ready` returns `503 SERVICE_UNAVAILABLE` when DB auth/connectivity fails |
| Common ops codes | `POLL_EMBED_TOKEN_REQUIRED`, `POLL_NOT_ACCEPTING_VOTES`, `POLL_VOTING_PAUSED`, `INVALID_OPTION_INDEX`, `INVALID_OPTION_INDICES`, `VOTE_SHAPE_MISMATCH`, `SELECTION_MODE_LOCKED`, `INCOMPATIBLE_SELECTION_MODE`, `LLM_DISABLED` |

## Workspace plans and limit errors

When **`BILLING_ENFORCE_LIMITS=true`**, several caps are enforced with **stable machine codes**; upgrade CTAs live in product UI / `details` where returned.

| Code family | Intended use | Example codes |
|---|---|---|
| `PLAN_LIMIT_*` | Feature not in current plan (automation, forensic timeline, Track C, etc.) | Shipped: **`PLAN_LIMIT_FORENSIC`** (`GET /poll/:id/replay`), **`PLAN_LIMIT_HEATMAP`** (`GET /poll/:id/heatmap`), **`PLAN_LIMIT_AUTOMATION`** (`PUT /poll/:id/moderation/batch`, plus `POST /poll` / `PUT /poll/:id` when setting non-empty `webhook_targets`, and `POST /poll/:id/clone` when source poll has non-empty `webhook_targets`), **`PLAN_LIMIT_RETENTION`** (`POST /poll`, `PUT /poll/:id` when setting non-null `retention_ttl_days` or `retention_legal_hold=true`, and `POST /poll/:id/clone` when source poll carries custom retention fields) when `BILLING_ENFORCE_LIMITS=true` and owner workspace is on `free`; details now include `plan`, `required_plan`, and `upgrade_hint` for CTA UX |
| `USAGE_LIMIT_*` | Numeric cap exceeded | Shipped: **`USAGE_LIMIT_ACTIVE_POLLS`** (HTTP **403**), **`USAGE_LIMIT_VOTES`** (HTTP **403**), **`USAGE_LIMIT_EXPORTS`** (HTTP **403**), **`USAGE_LIMIT_WS_SUBSCRIBERS`** (WebSocket close **1008** with reason string `USAGE_LIMIT_WS_SUBSCRIBERS`). **`USAGE_LIMIT_WS_FANOUT`**: logged when poll-live **update** broadcasts are **shed** (dropped) under per-poll outbound rate caps — clients should tolerate missing `update` ticks and refetch on the next successful push or timer. **Web app:** the public **Poll** page shows a localized status hint after that **1008** close so viewers know totals still refresh on the HTTP poll interval. **`USAGE_LIMIT_API_RATE`** (HTTP **429**): when **`BILLING_ENFORCE_LIMITS=true`**, authenticated traffic is keyed per user with ~2× sustained req/min tier burst (see monetization doc); anonymous traffic keeps **`HTTP_RATE_LIMIT_*`**. Metering row: `audit_logs.action=usage.api_rate_limited` with `details.workspace_user_id` (customer-visible on **`GET /profile/billing`** `usage.usageLedger`). **`USAGE_LIMIT_POLL_WEBHOOK_DELIVERY`**: logged when outbound signed **poll integration webhook** POST attempts exceed the **per-workspace per UTC minute** tier cap (`poll.webhook.delivery_shed`); deliveries are skipped (async path, no HTTP envelope to callers). **`USAGE_LIMIT_CAMPAIGN_ATTRIBUTION`**: logged when **`GET /poll/:id`** UTM-bearing views would exceed the owner workspace **per UTC day** campaign-attribution increment cap (`poll.campaign_attribution_shed`); **`impressionCount`** / hourly views still increment, but **`impressionAttribution`** is not updated for that view (public HTTP **200**). |
| `BILLING_*` | Payment or subscription state blocks expansion | `BILLING_PAST_DUE`, `BILLING_LICENSE_EXPIRED` (shipped on premium-gated selfhost-pro flows: replay, heatmap, moderation batch automation, webhook automation fields including clone-from-webhook-config path, and retention policy fields including clone-from-custom-retention path when license state is `expired`) |

**HTTP mapping (draft):** use `403` when the caller is authenticated but the plan forbids the capability; `429` when a rate or concurrency cap applies; `402` only if product standardizes “payment required” for past-due (optional). WebSocket subscribe failures use close **1008** with the reason string above (no JSON envelope on WS upgrade).

**Operator guardrails for remaining premium work:**
- New creator-facing premium features should ship with an explicit entitlement decision in the same change: paid-only, intentionally free, or enterprise-only. Do not leave roadmap-only features ungated by default and backfill later.
- Shed-only meters such as **`USAGE_LIMIT_WS_FANOUT`** and **`USAGE_LIMIT_POLL_WEBHOOK_DELIVERY`** do not produce a direct HTTP error envelope for the end user, so operator docs and customer-visible billing history should be updated whenever their behavior or metering semantics change.
- When a new metered action is added to **`usage.usageLedger`**, add matching **`usage.usageReconcile`** coverage in the same pass so `/profile/billing` remains explainable against raw `audit_logs`.
- For `selfhost-pro`, treat license-expiry enforcement as an audit checklist item on every new premium or selfhost-only path, not just the currently shipped replay/heatmap/automation/retention subset.
- Near-term implementation priority: complete the customer-facing `Settings` billing surface from existing `/profile/billing` fields before adding broader billing taxonomy or new backend billing endpoints.

See [MONETIZATION-AND-PACKAGING.md](MONETIZATION-AND-PACKAGING.md) for limit numbers and [OPERATIONS.md](OPERATIONS.md) for degraded-mode behavior during billing drift.

**Polar (billing):** `GET /billing/webhooks/info` (capability + **`deliveriesStoredCount`** / **`lastStoredDelivery`** from `polar_webhook_deliveries`), `POST /billing/webhooks/polar` — raw JSON body (`Buffer`), Standard Webhooks via `@polar-sh/sdk` `validateEvent`, gated by `ENABLE_POLAR_WEBHOOKS` + `POLAR_WEBHOOK_SECRET`. **`POST /admin/billing/reconcile-polar`** (admin auth) fetches Polar subscription state with **`POLAR_ACCESS_TOKEN`** when webhooks drift (see [POLAR-BILLING.md](POLAR-BILLING.md)).

<details>
<summary>Sequelize error mapping</summary>

| Sequelize condition | API status/code |
|---|---|
| `ValidationError` | `400 VALIDATION_ERROR` |
| Unique violation | `409 DUPLICATE_KEY` |
| Foreign key violation | `409 FOREIGN_KEY_VIOLATION` |
| Connection failure | `503 DATABASE_UNAVAILABLE` |
| Statement timeout | `503 DATABASE_TIMEOUT` |

</details>

## Auth and Access Matrix

| Route family | Accepted auth | Special rules |
|---|---|---|
| Public poll reads | none, or embed token when gated | Owner JWT (matching `creatorUserId`) can bypass embed gate on poll/meta/heatmap/export |
| Poll owner actions (`PUT`/`DELETE`/`clone`) | poll `api_key` or owner JWT | Supports panic mode and optional auto-advance; `PUT` allows collaborator JWT edits for draft polls when included in `shared_editor_user_ids` |
| Distribution presets (creator UX) | `GET /poll/mine` data + public poll URLs | `My Polls` renders channel-ready share presets and CTA snippets by composing poll links with UTM params (`utm_source`, `utm_medium`, `utm_campaign`); each poll row includes **`hourly_votes_by_hour_utc`** (24 bins) and **`weekday_votes_by_dow_utc`** (7 bins, UTC, non-quarantined votes) for list-level sparklines |
| Embed read URL minting | `POST /poll/:id/embed-read-url` with poll `api_key` or owner JWT | Issues short-lived signed read URLs (`embed_exp`, `embed_sig`) for browser sources without exposing `api_key` |
| Vote endpoint | none by default, embed token when gated | Enforces phase/pause/friction/rate-limit checks; signed read grants are read-only and do not replace vote token checks |
| WebSocket updates | embed token, signed read grant (`embed_exp`,`embed_sig`), or owner JWT via `ws_bearer` for gated polls | Emits `update`, `panic`, `deleted` events |
| Admin endpoints | `ADMIN_TOKEN` and role-scoped JWT flow | `mod` can manage polls + view dashboard/status; only `admin`/`superadmin` can manage users, export, and system toggles; **`GET /admin/status`** includes retention policy fields (`poll_retention_*`, audit/rejected-vote retention windows and legal-hold flags) plus **`webhookDeliveryTelemetry`** (rolling in-process poll webhook attempts / ok / non-2xx / failed / shed counters for quick runtime checks; resets on API restart), and **`GET/POST /admin/retention-policy`** exposes/updates those values; **`POST /admin/billing/reconcile-polar`** repairs **`workspaces.billing_plan`** (and owner **`users`** mirror) vs Polar API when **`POLAR_ACCESS_TOKEN`** is set |

### Contributor handoff

- **Shipped now:** poll webhook helper fields (`streamer_context`, `results_snapshot`, `owner_snapshot`, `owner_events`), per-target webhook flags in create/update flows, creator UI toggles, Developer payload examples, operator safety guidance, and `GET /admin/status` runtime webhook counters.
- **Current limitation:** `GET /admin/status` `webhookDeliveryTelemetry` is intentionally **best-effort and in-process only**. It is useful for quick live checks but resets on restart and does not aggregate across multiple API instances.
- **Next backend slice:** keep the existing Admin Status shape/UI, but move webhook runtime visibility onto durable storage or rollups so operators can see restart-safe and multi-instance-safe delivery / shed history.

## Poll Lifecycle and Moderation Flow

```text
Create -> Open voting -> (Optional) quarantine queue -> Approve/reject -> Export / Reveal / Archive
```

| Stage | Endpoint | Key outputs/controls |
|---|---|---|
| Create | `POST /poll` | Returns `data.id` and creator `data.api_key`; supports schedule, boosted voting, friction, webhooks, vanity slug, optional `selection_mode` (`multi` is mutually exclusive with boosted voting and write-ins), optional per-poll `retention_ttl_days` (auto-delete window after expiration), and optional `retention_legal_hold` (pause auto-delete). `webhook_targets[]` accepts optional `hint_locale` (`en` / `en-gb` / `es`), `include_results_snapshot`, and `include_owner_snapshot` (sensitive; trusted endpoints only) for per-target webhook shaping. `vote_eligibility` accepts `anonymous`, `account`, and `platform_linked` (scaffold mode). When `vote_eligibility` is `account` or `platform_linked`, request must include `account_vote_consent_ack=true`; when `platform_linked`, also include `platform_identity_provider` and `platform_identity_consent_version` (consent metadata scaffold). |
| Read | `GET /poll/:id` | Returns poll state, integrity signals, owner moderation counters, and votes (minus quarantined public totals). Private `show_notes` are visible to poll owner and mod/admin/superadmin viewers. `utm_source` / `utm_medium` / `utm_campaign` query params are tracked for impression attribution analytics, and anonymous hourly view rollups feed creator conversion + per-option funnel summaries. Includes retention metadata `retention_ttl_days`, `retention_legal_hold`, and computed `auto_delete_at_ms` (UTC ms, nullable; null while legal hold is active). For platform-linked eligibility scaffolding, responses also include `platform_identity_provider`, `platform_identity_consent_version`, and `platform_identity_consent_captured_at_ms`. When the caller JWT owns the poll, **`metrics`** also includes **`option_hourly_votes_utc`** (per configured option, 24 UTC clock-hour bins), **`vote_velocity_by_minute_utc`** (`minute_utc` ISO + `vote_count`, export-compatible, capped at **4000** most recent voting minutes), **`vote_velocity_by_minute_utc_truncated`**: `true` when that cap is hit, and **`option_vote_velocity_by_minute_utc`** (per configured option: same `{ minute_utc, vote_count }[]` shape on a shared grid of up to **120** most recent distinct UTC minutes that had any vote, chronological, zeros filled); owner-only `moderation_counters` include signed-in mix fields `votes_account_linked_last_24h`, `votes_anonymous_last_24h`, and `quarantined_votes_pending_account_linked` alongside minute-rate and burst summaries |
| Update | `PUT /poll/:id` | Phase/schedule/notes/pause/write-in/webhook/boost settings; `selection_mode` only while **draft**; supports `retention_ttl_days` updates (`null` clears to global default) and `retention_legal_hold` toggle; optional `panic=true`. `webhook_targets[]` accepts optional `hint_locale` (`en` / `en-gb` / `es`), `include_results_snapshot`, and `include_owner_snapshot` so each destination can receive localized command hints plus optional snapshots. Treat `include_owner_snapshot` as trusted-receiver-only. When patching `vote_eligibility=account` or `vote_eligibility=platform_linked`, include `account_vote_consent_ack=true`; for `platform_linked`, include `platform_identity_provider` and `platform_identity_consent_version` (consent metadata scaffold). |
| Moderate | Quarantine + batch endpoints | `approve`, `reject`, `revert`, and wave rollback/restore with audit events |
| Media policy hooks | `POST /poll/:id/media/report`, `POST /admin/polls/:id/media/takedown`, `POST /admin/polls/:id/media/restore` | Public report path marks media as reported; admin/mod can takedown or restore with audit trail |
| Export | `GET /poll/:id/export` | `include=summary|votes`; JSON includes UTC metadata and phase history; CSV is data-only |

<details>
<summary>Voting validation and anti-abuse details</summary>

| Area | Rules |
|---|---|
| Input shape | Single-choice: exactly one of `option` or `option_index`. Multi (`selection_mode=multi`): `option_indices` (unique 0-based indices). Optional `boost_weight`, `pow_nonce`, `chat_channel_id`, `idempotency_key` |
| Platform-linked identity | When poll `vote_eligibility=platform_linked`: signed-in JWT is required, poll must have `platform_identity_provider` configured, and vote requests must include `X-Platform-Subject` (optional `X-Platform-Provider` must match configured provider when sent). Duplicate prevention is keyed by poll + provider + hashed platform subject (not just app `userId`). Error codes: `PLATFORM_IDENTITY_NOT_CONFIGURED`, `PLATFORM_IDENTITY_REQUIRED`, `PLATFORM_IDENTITY_PROVIDER_MISMATCH` |
| Identity-linked UX copy | Create/edit/vote UI surfaces include explicit legal/privacy copy when `vote_eligibility` is `account` or `platform_linked`, with region-aware variants driven by `GET /telemetry/consent-region` (`eu` / `non-eu` / `unknown`) so operators can align consent/disclosure and retention policy text before rollout |
| Vote webhook callback shape | `event=vote` webhook payload now includes `vote_eligibility`, `voter_user_id` (nullable), `poll_url`, `results_url`, `streamer_context` (poll title, phase, pause/archived flags, `selection_mode`, `schedule_utc_ms` with `open_at` / `lock_at` / `reveal_at` / `expires_at` as UTC epoch ms or null — snapshot at delivery enqueue time), optional per-target **`results_snapshot`** when `webhook_targets[].include_results_snapshot` is true (public option tallies; excludes quarantined votes; honors **`results_delay_seconds`** the same way as anonymous `GET /poll/:id`), optional per-target **`owner_snapshot`** when `webhook_targets[].include_owner_snapshot` is true (moderation-style counters, trust-stack summaries `trust_ip_burst` / `trust_chat_burst`, and delayed-vote pending count — **sensitive**; same aggregate SQL family as owner `GET /poll/:id`), `command_hints` (`chat_vote_short`, `chat_results_short`, `command_aliases`, `capability_flags`, `contract_version`, `hint_locale`, `supported_hint_locales`, `hint_packs`), `platform_identity_provider` (nullable), `platform_identity_subject_hash` (nullable), and `moderation` (`{ quarantined, reason?, trust_risk_score? }`) so bot/automation consumers can branch behavior without extra poll fetches |
| Cross-event callback helper fields | All poll webhook events (`vote`, `poll_updated`, `poll_deleted`) include `poll_path`, `results_path`, `streamer_context` (same shape on every event), and `command_hints` defaults in `data` so receivers can share one routing/templating path. Defaults include `command_aliases` (`vote[]`, `results[]`), `capability_flags` (including `supports_hint_locale_override`, `supports_hint_packs`, `supports_supported_hint_locales`, `supports_contract_version`, `supports_streamer_context`, `supports_webhook_results_snapshot`, `supports_webhook_owner_snapshot`), `contract_version` (`2026-04-webhook-command-hints-v1`), `hint_locale` (from `POLL_WEBHOOK_HINT_LOCALE` or caller `command_hints.hint_locale` when valid: `en` / `en-gb` / `es`), `supported_hint_locales` (currently `en`, `en-gb`, `es`), and `hint_packs` (full pack map for all supported locales). **`results_snapshot`** is included only on deliveries to targets with `include_results_snapshot: true`; **`owner_snapshot`** only when `include_owner_snapshot: true` in stored `webhook_targets[]` (create/update poll). Callers may override top-level hint strings and nested maps per event payload; missing nested keys are backfilled from defaults and event-specific fields remain additive |
| Webhook safety (operator) | Treat `include_owner_snapshot` with the same or stricter trust boundary as the webhook secret: enable it only for endpoints you fully control, rotate secrets if receiver ownership changes, and avoid forwarding owner snapshots into shared chat bots or third-party automation hops. `owner_snapshot` carries coarse counts only, but trust-stack burst summaries and delayed-vote counters can still expose operational traffic patterns. |
| Webhook replay hardening | Signed poll webhooks include `event_id` in JSON body and `X-Asking-Webhook-Event-Id` header. Receivers should reject duplicate `event_id` values (or duplicate header values) inside their acceptance window after validating `X-Asking-Webhook-Timestamp` and `X-Asking-Webhook-Signature` |
| Receiver verification example | `scripts/verify-poll-webhook-example.mjs` shows timestamp skew + signature validation + event-id extraction flow for replay protection |
| Receiver command-hints negotiation | [WEBHOOK-COMMAND-HINTS-RECEIVERS.md](WEBHOOK-COMMAND-HINTS-RECEIVERS.md) — branch on `data.command_hints.contract_version`, use `capability_flags`, fallback for unknown versions, additive vs breaking changes |
| Boost checks | `BOOST_WEIGHT_DISABLED`, `INVALID_BOOST_WEIGHT` |
| Friction checks | `POW_REQUIRED`, `POLL_SOFT_THROTTLED`, `CHANNEL_RATE_LIMITED` |
| State checks | `DUPLICATE_VOTE`, `POLL_EXPIRED`, `POLL_ARCHIVED`, plus non-open/paused vote rejection |
| Quarantine behavior | Near-threshold soft-throttle votes can be quarantined and hidden from public totals until reviewed |

</details>

## Optional Integrations

| Integration | Endpoint/config | Notes |
|---|---|---|
| Swagger UI | `GET /api-docs` + `ENABLE_API_DOCS=true` in production | Curated route docs |
| Platform webhooks | `POST /platform/webhooks/:provider` + `ENABLE_PLATFORM_WEBHOOKS=true` | Requires `x-platform-webhook-token` = `PLATFORM_WEBHOOK_SHARED_SECRET` |
| Webhook providers | `twitch`, `youtube`, `kick`, `discord`, `telegram`, `slack`, `x`, `tiktok`, `facebook`, `instagram` | Grouped streaming/community and social sources |
| LLM gateway | `/llm/*` + provider config (`ollama` or `lmstudio`) | `INCIDENT_MODE` disables routes with `503 LLM_DISABLED` |
| Incident-mode outbound controls | Poll webhooks + integration sinks (`notify`, `audit`, `error`) | When `INCIDENT_MODE=true`, outbound deliveries are skipped to reduce blast radius during instability |
| LLM auth | `OLLAMA_API_KEY` / `LMSTUDIO_API_KEY` and optional `LLM_GATEWAY_TOKEN` | Supports upstream and gateway token layers |
