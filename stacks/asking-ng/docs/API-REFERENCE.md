# asking-ng API reference (operator view) 🧩

## Purpose

Operator-focused API summary for common routes, auth rules, error patterns, and optional integrations.

## Use This When

- You need a route family map without digging through code.
- You are validating auth/error behavior during deploys or incident response.
- You want quick integration guardrails for webhooks or LLM gateway setup.

## Related Docs

- [../README.md](../README.md)
- [API-MIGRATION-TRACKER.md](API-MIGRATION-TRACKER.md)
- [CI-REPO-WORKFLOW.md](CI-REPO-WORKFLOW.md)
- [OPERATIONS.md](OPERATIONS.md)
- [MONETIZATION-AND-PACKAGING.md](MONETIZATION-AND-PACKAGING.md)
- [POLAR-BILLING.md](POLAR-BILLING.md)
- [OSS-AND-COMMERCIAL-POSITIONING.md](OSS-AND-COMMERCIAL-POSITIONING.md)

For migration status and refactor phases, see [API-MIGRATION-TRACKER.md](API-MIGRATION-TRACKER.md).

## At-a-Glance Endpoint Map

| Goal | Primary endpoints | Notes |
|---|---|---|
| Service health | `GET /healthcheck`, `GET /ready`, `GET /info`, `GET /status/history` | `/ready` validates DB connectivity; in `INCIDENT_MODE`, `/status/history` serves a static degraded fallback if DB history query fails |
| Session billing links | `GET /profile/billing` | JWT session; returns Polar portal/checkout URLs from `POLAR_*` when configured; with **`BILLING_ENFORCE_LIMITS`**, includes **`usage`** meters (polls, votes, exports, WS caps, optional UTC-minute **poll webhook** delivery counter + **`warnings`**) |
| Poll creation and reads | `POST /poll`, `GET /poll/:id`, `GET /poll/:id/meta`, `GET /poll/:id/export`, `POST /poll/:id/embed-read-url`, `GET /s/:slug` | Supports phase schedule, boosted voting, vanity slug, embed gates, per-poll `theme_preset`, optional `selection_mode` (`single` / `multi`), and UTM impression attribution |
| Owner updates | `PUT /poll/:id`, `DELETE /poll/:id`, `POST /poll/:id/clone` | Auth via poll `api_key` or owner JWT; draft polls can grant collaborator edits via `shared_editor_user_ids` |
| Voting and realtime | `PUT /poll/:id/vote`, `GET /ws/poll/:id` | Includes anti-abuse controls and websocket refetch model |
| Moderation and audit | `GET /poll/:id/quarantine`, `PUT /poll/:id/quarantine/:voteId`, `PUT /poll/:id/moderation/batch`, `GET /admin/audit-logs` | Quarantined votes stay out of public totals until approved |
| Optional integrations | `GET /api-docs`, `POST /platform/webhooks/:provider`, `/llm/*` | Feature-gated with env flags; `INCIDENT_MODE` disables LLM and suppresses outbound webhook deliveries |

## Response and Error Model

| Topic | Behavior |
|---|---|
| Error envelope | `{"error":{"code":"<UPPER_SNAKE>","message":"<human>","details"?:...},"requestId":"<uuid>"}` |
| Success shape | Poll routes keep legacy success wrapper `{"status":"success","data":...}` where already established |
| Rate limits | `429` with codes like `RATE_LIMIT_AUTH`, `RATE_LIMIT_ADMIN`, `RATE_LIMIT_CREATE_POLL`, `RATE_LIMIT_VOTE`, `RATE_LIMIT_LLM` |
| Readiness failure | `GET /ready` returns `503 SERVICE_UNAVAILABLE` when DB auth/connectivity fails |
| Common ops codes | `POLL_EMBED_TOKEN_REQUIRED`, `POLL_NOT_ACCEPTING_VOTES`, `POLL_VOTING_PAUSED`, `INVALID_OPTION_INDEX`, `INVALID_OPTION_INDICES`, `VOTE_SHAPE_MISMATCH`, `SELECTION_MODE_LOCKED`, `INCOMPATIBLE_SELECTION_MODE`, `LLM_DISABLED` |

## Workspace plans and limit errors (partially wired)

When **`BILLING_ENFORCE_LIMITS=true`**, several caps are enforced with **stable machine codes**; upgrade CTAs live in product UI / `details` where returned.

| Code family | Intended use | Example codes |
|---|---|---|
| `PLAN_LIMIT_*` | Feature not in current plan (automation, forensic timeline, Track C, etc.) | `PLAN_LIMIT_AUTOMATION`, `PLAN_LIMIT_FORENSIC` |
| `USAGE_LIMIT_*` | Numeric cap exceeded | Shipped: **`USAGE_LIMIT_ACTIVE_POLLS`** (HTTP **403**), **`USAGE_LIMIT_VOTES`** (HTTP **403**), **`USAGE_LIMIT_EXPORTS`** (HTTP **403**), **`USAGE_LIMIT_WS_SUBSCRIBERS`** (WebSocket close **1008** with reason string `USAGE_LIMIT_WS_SUBSCRIBERS`). **`USAGE_LIMIT_WS_FANOUT`**: logged when poll-live **update** broadcasts are **shed** (dropped) under per-poll outbound rate caps — clients should tolerate missing `update` ticks and refetch on the next successful push or timer. **Web app:** the public **Poll** page shows a localized status hint after that **1008** close so viewers know totals still refresh on the HTTP poll interval. **`USAGE_LIMIT_API_RATE`** (HTTP **429**): when **`BILLING_ENFORCE_LIMITS=true`**, authenticated traffic is keyed per user with ~2× sustained req/min tier burst (see monetization doc); anonymous traffic keeps **`HTTP_RATE_LIMIT_*`**. **`USAGE_LIMIT_POLL_WEBHOOK_DELIVERY`**: logged when outbound signed **poll integration webhook** POST attempts exceed the **per-workspace per UTC minute** tier cap (`poll.webhook.delivery_shed`); deliveries are skipped (async path, no HTTP envelope to callers). |
| `BILLING_*` | Payment or subscription state blocks expansion | `BILLING_PAST_DUE`, `BILLING_LICENSE_EXPIRED` |

**HTTP mapping (draft):** use `403` when the caller is authenticated but the plan forbids the capability; `429` when a rate or concurrency cap applies; `402` only if product standardizes “payment required” for past-due (optional). WebSocket subscribe failures use close **1008** with the reason string above (no JSON envelope on WS upgrade).

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
| Admin endpoints | `ADMIN_TOKEN` and role-scoped JWT flow | `mod` can manage polls + view dashboard/status; only `admin`/`superadmin` can manage users, export, and system toggles; **`POST /admin/billing/reconcile-polar`** repairs **`workspaces.billing_plan`** (and owner **`users`** mirror) vs Polar API when **`POLAR_ACCESS_TOKEN`** is set |

## Poll Lifecycle and Moderation Flow

```text
Create -> Open voting -> (Optional) quarantine queue -> Approve/reject -> Export / Reveal / Archive
```

| Stage | Endpoint | Key outputs/controls |
|---|---|---|
| Create | `POST /poll` | Returns `data.id` and creator `data.api_key`; supports schedule, boosted voting, friction, webhooks, vanity slug, optional `selection_mode` (`multi` is mutually exclusive with boosted voting and write-ins) |
| Read | `GET /poll/:id` | Returns poll state, integrity signals, owner moderation counters, and votes (minus quarantined public totals). Private `show_notes` are visible to poll owner and mod/admin/superadmin viewers. `utm_source` / `utm_medium` / `utm_campaign` query params are tracked for impression attribution analytics, and anonymous hourly view rollups feed creator conversion + per-option funnel summaries. When the caller JWT owns the poll, **`metrics`** also includes **`option_hourly_votes_utc`** (per configured option, 24 UTC clock-hour bins), **`vote_velocity_by_minute_utc`** (`minute_utc` ISO + `vote_count`, export-compatible, capped at **4000** most recent voting minutes), and **`vote_velocity_by_minute_utc_truncated`**: `true` when the cap is reached |
| Update | `PUT /poll/:id` | Phase/schedule/notes/pause/write-in/webhook/boost settings; `selection_mode` only while **draft**; optional `panic=true` |
| Moderate | Quarantine + batch endpoints | `approve`, `reject`, `revert`, and wave rollback/restore with audit events |
| Media policy hooks | `POST /poll/:id/media/report`, `POST /admin/polls/:id/media/takedown`, `POST /admin/polls/:id/media/restore` | Public report path marks media as reported; admin/mod can takedown or restore with audit trail |
| Export | `GET /poll/:id/export` | `include=summary|votes`; JSON includes UTC metadata and phase history; CSV is data-only |

<details>
<summary>Voting validation and anti-abuse details</summary>

| Area | Rules |
|---|---|
| Input shape | Single-choice: exactly one of `option` or `option_index`. Multi (`selection_mode=multi`): `option_indices` (unique 0-based indices). Optional `boost_weight`, `pow_nonce`, `chat_channel_id`, `idempotency_key` |
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
