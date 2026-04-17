# Creator & streamer roadmap 🎬

Product ideas for **live audiences**, **moderation**, **integrations**, **analytics**, **branding**, **team workflows**, and **on-air safety**. Not all items need to ship; this file is a **backlog by theme** only. For what the app already does (API, env, UX), see [README.md](../README.md).

## Commercial packaging (tiers and limits)

When scoping a feature, map it to a **bundle** and plan tier using the canonical spec—not this backlog alone:

- [MONETIZATION-AND-PACKAGING.md](MONETIZATION-AND-PACKAGING.md) — `free` / `cloud-team` / `cloud-pro` / `selfhost-pro` / `enterprise-custom`, hard limits, add-ons, migration, regulated tracks.
- [OSS-AND-COMMERCIAL-POSITIONING.md](OSS-AND-COMMERCIAL-POSITIONING.md) — what remains OSS-friendly vs paid modules and how to communicate tier changes.

## Chat & platform glue

- **Bot integrations**: continue command contract expansion (shipped baseline: cross-event `command_hints` + `hint_packs` for `en` / `en-gb` / `es`, server default `POLL_WEBHOOK_HINT_LOCALE`, webhook-target `hint_locale`, **`include_results_snapshot`**, **`include_owner_snapshot`**, and **`include_owner_events`** in `webhook_targets[]`, optional **`data.results_snapshot`** / **`data.owner_snapshot`** / **`data.owner_events`** on opted-in URLs, locale-aware capability flags including `supports_owner_events`, explicit `contract_version`, receiver guide `docs/WEBHOOK-COMMAND-HINTS-RECEIVERS.md`, version log `docs/POLL-WEBHOOK-CONTRACT-VERSIONS.md`, **`data.streamer_context`** on all poll webhook events, creator UI controls for sensitive webhook helpers without raw JSON, and a lightweight **Admin Status** runtime panel for recent webhook attempts / non-2xx / failures / sheds; next: promote runtime webhook visibility from per-process memory to durable multi-instance rollups, then continue moderation-rich payload expansions where product allows) and broader streamer helper payloads for automation workflows.

### Current handoff state

- **Shipped and verified:** per-target webhook helper flags (`hint_locale`, `include_results_snapshot`, `include_owner_snapshot`, `include_owner_events`), receiver docs + contract-version log, creator UI toggles in `Home` / `MyPolls`, Developer webhook payload examples, operator safety notes, and Admin Status runtime counters for recent webhook attempts / non-2xx / failures / sheds.
- **Known temporary implementation:** Admin Status webhook visibility is **in-process memory only** (`webhookDeliveryTelemetry` on `GET /admin/status`). It resets on API restart and is not suitable for multi-instance or durable audit/history views.
- **Recommended next slice for another agent:** replace the current per-process webhook runtime counters with **durable rollup-backed admin visibility**. Keep the existing Admin Status panel, but source it from audit-log / rollup data that survives restarts and works across multiple API instances.
- **After that:** resume webhook payload expansion only if it stays additive and trusted-receiver-only; prefer moderation-rich owner helpers over public payload widening.
- **External identity (optional)**: link votes to platform user id when the creator opts in, with consent and retention policy in stack docs.

### Owner-only webhook payload expansion (shipped additive slice)

- **Goal:** add richer owner-side automation context without exposing raw voter identity or widening receiver trust beyond the existing owner-snapshot posture.
- **Opt-in model:** additive per-target flag in `webhook_targets[]` only (`include_owner_events`, default off), same trust boundary as webhook secret + existing `include_owner_snapshot`.
- **Shipped additive data block:** `data.owner_events` (optional object):
  - `captured_at_ms`, `window_ms`
  - `safeguard_tags` (array): derived trust labels from `trustStackSafeguardTags()` for routing/alerting
  - `quarantine_recent` (array, newest first, capped): `{ vote_id, reason, risk_score, created_at_ms, state }`
  - `moderation_actions_recent` (array, capped): `{ action, actor_role, count, created_at_ms }`
  - `truncated`: `{ quarantine_recent, moderation_actions_recent }`
- **Privacy / safety constraints:**
  - no raw IPs, account ids, user ids, device fingerprints, or unbounded free-text notes
  - keep coarse aggregates and internal opaque ids only (`vote_id` already appears in owner-visible flows)
  - enforce small bounded arrays with explicit truncation semantics
- **Failure behavior:** if owner-events query/build fails, still deliver webhook envelope and other optional snapshots; omit `owner_events` for that delivery and log the fetch failure server-side.
- **Capability and versioning:** shipped behind `capability_flags.supports_owner_events` in `command_hints`; kept under the current `contract_version` because the block is strictly additive and optional.
- **Tiering / entitlement:** aligns with the automation/trust feature posture. Treat future owner-only webhook expansions the same way: decide paid-vs-free entitlement before shipping so premium checks and docs land in the same change.
- **Rollout status:**
  1. `@asking-ng/contracts`: done
  2. API builder from existing moderation/trust surfaces: done
  3. Receiver docs + version log: done
  4. UI toggle/help text in `Home` and `MyPolls`: done
  5. Tests for contract/API opt-in behavior and fallback: done
  6. Developer payload examples + operator safety notes: done
  7. Admin Status lightweight runtime visibility panel: done
  8. Durable multi-instance runtime visibility: next

---

## Competitive parity backlog (strawpoll/slido-class)

- **Poll type expansion**: ranked choice, rating scale, quiz mode, and optional free-text answers with moderation support.
- **Identity tier evolution**: complete `platform_linked` with provider/OAuth binding, consent UX, and tier-aware moderation/reporting.

---

## Gamification and audience energy

Ideas to increase **repeat participation** and **show moments** without implying real-money wagering unless a regulated track is explicitly enabled (see [MONETIZATION-AND-PACKAGING.md](MONETIZATION-AND-PACKAGING.md) — Track B/C posture). Map each to a **bundle** when scoping (`Streamer engagement`, `Trust & safety`, `Team workflow`, `Brand / creator`).

### Lightweight (low regulatory surface)

- **Vote milestones & celebrations**: configurable thresholds (e.g. “1k votes”) with overlay-safe animations; optional sound/haptic off by default.
- **Streaks & recurring viewers**: optional **account-linked** streak counters per poll or per channel preset; reset rules and anti-farm cooldowns; clear “for fun only” copy.
- **Badges / flair (cosmetic)**: owner-defined or template badges for voters who meet rules (e.g. first N voters, voted every phase); **no third-party resale value** (Track B–aligned).
- **Crowd confidence / “energy” meters**: non-binding visualizations from vote velocity or distribution; no payouts; pairs with analytics on **My Polls**.

### Mid-depth (product + moderation)

- **Quests and challenges**: time-boxed goals (“500 votes before intermission”) with mod-visible progress and optional **auto-advance** hooks to poll phases.
- **Drops and unlocks**: mod- or owner-triggered “unlock next question” / reveal gated on vote count or chat command (integrates with bot story later).
- **Leaderboards & seasons**: per-poll or per-show **opt-in** boards with TTL, pseudonymous handles, and **rate limits**; export-friendly summaries for creators; higher caps / automation on paid tiers if you meter API reads.
- **Quiz / play-along modes**: speed + accuracy scoring for quiz poll type (see **Poll type expansion**); public “top this round” without transferable prizes unless counsel approves.

### Heavier / platform-adjacent

- **Channel-points-adjacent flows**: only via official provider APIs and **Track C** packaging when you ship it; never manual “balance edits.”
- **Tips / cheers / paid visibility**: separate legal pass; often `cloud-pro` + enterprise if tied to money movement.

### Guardrails

- Prefer **opt-in** and **per-poll** toggles; default off for anonymous high-risk installs.
- Gamification signals must feed **trust** scoring where they could be farmed (synthetic streaks, bot swarms).
- i18n all player-facing strings; keep overlays **readable** and **reduced-motion** friendly.

---

## Trust, compliance, and anti-abuse parity

- **Legal sign-off ownership**: define and enforce formal legal/privacy approver ownership for region matrix changes before release.
- **Policy hardening** for identity-linking surfaces as regional/compliance requirements evolve.

---

## Suggested implementation order

1. **Chat & platform glue (small slices first):** finish richer bot command/callback flows and streamer automation helper contracts.
2. **Trust/compliance polish:** complete legal sign-off ownership and continue policy hardening for identity-linked modes.
3. **Competitive parity backlog:** start with poll type expansion (ranked/rating/quiz/free-text moderation), then continue identity-tier evolution.
4. **Gamification (phased):** ship **lightweight** items first (milestones, energy meters, cosmetic badges) behind poll flags; then **quests / drops / leaderboards** once identity + trust signals exist; reserve **provider-linked** or **paid-visibility** mechanics for later tiers and legal review.

---

## Implementation notes (for contributors)

- Prefer extending **`@asking-ng/contracts`** for any new wire shapes (phases, mod actions, analytics events).
- Upcoming poll formats (**ranked choice**, **rating scale**, **quiz**, **free-text**) can align with the reserved enum **`pollFormatExtensionSchema`** in `@asking-ng/contracts/poll` until vote/create APIs consume it.
- Large or risky integrations (platform OAuth, webhooks) should stay **off by default** and be documented in `stack.env.example` with clear security notes.
- **Distribution UX**: keep UTM campaign names and snippet text consistent between `MyPolls.tsx`, `Home.tsx` (post-create), and `Poll.tsx` (owner share block); prefer `shareUrlForPoll` / `shareUrlForPollResults` + `withUtm` over ad-hoc query strings (**Home** uses `homePostCreateTrackedPollShareUrl` so postcard copies match the selected preset); keep **public poll link**, **Web Share**, and **`apiUrl('poll/…/embed')` + `embed_token`** aligned across **My Polls**, **Poll** owner details, and **Home** “Access tokens & secrets” when a fresh embed token exists.
- **UTC weekday (`peak_dow_utc`):** format with **`client/src/lib/formatUtcWeekdayShort.ts`** + **`useLocaleTag()`** so list/metrics/dashboard stay consistent; avoid hard-coded English `Sun`–`Sat` arrays.
- **UTC clock hour (`peak_hour_utc`, hourly buckets 0–23):** format with **`client/src/lib/formatUtcHourAtTopOfHour.ts`** + **`useLocaleTag()`** (short timezone name via `Intl`); avoid concatenating a literal ` UTC` after hand-built `HH:00`.
- **Moderation queue copy:** keep new strings and key reuse consistent across Poll/My Polls/Admin surfaces.
- **Trust stack**: keep burst thresholds in **`lib/trustStackSignals.ts`** (single source) for **`trust_ip_burst`** / **`trust_chat_burst`** owner fields and **`trustStackSafeguardTags()`** on **`integrity_panel`**; vote path uses **`reasonFromTrustSignals`** + **`trustRiskScore`** in `voteOnPoll.service.ts`.
- **Billing usage visibility**: keep `GET /profile/billing` usage taxonomy aligned end-to-end: `usage.usageLedger` latest-first rows, `usage.usageLedgerDaily` UTC-day rollups, and `usage.usageReconcile` parity checks should reflect API metering writes (`usage.data_export`, `usage.campaign_attribution_shed`, `usage.poll_webhook_delivery_shed`, `usage.ws_fanout_shed`, `usage.api_rate_limited`) so creator-facing billing history remains explainable.
- **Billing scope hygiene**: when a new feature introduces a metered action, decide at design time whether users need to see that action in the ledger and whether raw-log parity checks must be added alongside it; avoid adding silent billable events that are not explainable in `GET /profile/billing`.
- **Current UX priority**: before adding more billing taxonomy, make `client/src/pages/Settings.tsx` the customer-facing billing hub for existing `/profile/billing` data (plan, upgrade/portal links, selfhost license state, usage summary, recent ledger, daily rollups, reconcile health).
