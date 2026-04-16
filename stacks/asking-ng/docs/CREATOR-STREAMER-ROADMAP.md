# Creator & streamer roadmap 🎬

Product ideas for **live audiences**, **moderation**, **integrations**, **analytics**, **branding**, **team workflows**, and **on-air safety**. Not all items need to ship; this file is a **backlog by theme** only. For what the app already does (API, env, UX), see [README.md](../README.md).

## Commercial packaging (tiers and limits)

When scoping a feature, map it to a **bundle** and plan tier using the canonical spec—not this backlog alone:

- [MONETIZATION-AND-PACKAGING.md](MONETIZATION-AND-PACKAGING.md) — `free` / `cloud-team` / `cloud-pro` / `selfhost-pro` / `enterprise-custom`, hard limits, add-ons, migration, regulated tracks.
- [OSS-AND-COMMERCIAL-POSITIONING.md](OSS-AND-COMMERCIAL-POSITIONING.md) — what remains OSS-friendly vs paid modules and how to communicate tier changes.

### Shipped creator-facing UX (limits and polish)

Single place for **what users already see** that ties to plans, limits, or trust surfaces (update here when you add more; link out for wire/error details):

- **Plan usage warnings:** `GET /profile/billing` **usage.warnings** at 80% / 95% on **Home**, **My Polls**, and **Developer**.
- **Concurrent viewer cap:** **Poll** live view explains WebSocket disconnect when the subscriber cap is hit (`1008` / `USAGE_LIMIT_WS_SUBSCRIBERS`); codes and limits in [API-REFERENCE.md](API-REFERENCE.md) and MONETIZATION.
- **My Polls moderation queue:** Vote row copy is fully localized—metadata via **`myPolls.quarantineVoteMeta`**, source identifiers via **`myPolls.quarantineSourceLine`**, and per-vote status reuses **`myPolls.queuePending` / `queueApproved` / `queueRejected`** so row labels match the queue filter tabs.
- **My Polls list analytics:** Peak weekday (UTC) uses **`formatUtcWeekdayShort`**; peak clock hour uses **`formatUtcHourAtTopOfHour`** (same helpers as **Poll** metrics and **Admin** sparklines); top UTM campaign uses **`myPolls.topCampaign`**; poll **created** timestamp uses **`toLocaleString(localeTag)`**.
- **Poll owner metrics (signed-in):** Velocity / completion / coverage / margin / time-to-first lines use **`poll.metrics.*`** keys; hourly range and sparkline bucket labels use **`formatUtcHourAtTopOfHour`** so **`poll.metrics.hourlyAxis`** and **`admin.dashboard.kpi.hourlySparklineAxis`** pass localized start/end without a second hard-coded `(UTC)` suffix.
- **Results-only overlay (`/…/results`):** Toolbar strings (refresh interval, scene-safe / contrast / fullscreen controls, group **`aria-label`**) use **`poll.resultsToolbarAria`** and **`poll.resultsRefresh*`** / **`poll.resultsSceneSafe*`** / **`poll.resultsContrast*`** / **`poll.resultsFullscreen*`** keys.

---

## Chat & platform glue

- **Bot integrations**: extend beyond today’s compact meta + exports (e.g. signed vote callbacks, richer command contracts, streaming-specific helpers).
- **External identity (optional)**: link votes to platform user id when the creator opts in, with consent and retention policy in stack docs.

---

## Competitive parity backlog (strawpoll/slido-class)

- **Poll type expansion**: ranked choice, rating scale, quiz mode, and optional free-text answers with moderation support (multi-select for fixed options is implemented as `selection_mode=multi` + `option_indices` on `PUT /poll/:id/vote`).
- **Identity tiers**: `vote_eligibility` per poll — **`anonymous`** (default) or **`account`** (JWT required; one ballot per user). Platform-linked / OAuth identity is still TBD.

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

- **Fraud controls v1**: velocity anomalies, risk scoring, and mod-visible suspicious vote markers — **partial**: per-poll soft throttle (existing), optional stack **IP** + **chat-channel** short-window burst quarantine + combined reason codes + **`trust_risk_score`**, moderation queue + batch rollback (existing). Owner-facing queue UI copy is listed under **Shipped creator-facing UX** above.
- **Retention controls**: per-poll and global retention windows (including optional auto-delete).
- **Consent/legal UX**: clear opt-in copy when identity linking is enabled, plus region-aware privacy notes — **partial**: **`home.voteEligibility.accountConsentNote`** on **Home** (before create), **My Polls** (draft), and **Poll** owner sharing; **`poll.accountGatedPrivacy`** under the sign-in prompt when a signed-out viewer opens an account-gated poll.

---

## Suggested implementation order

1. **MVP parity**: poll type expansion + clone workflows — **My Polls** “clone for next slot” is i18n’d; **Home** starter gallery uses **`home.pollTemplate.*`** (label, title, newline-separated options, notes) per locale.
2. **Creator UX**: reusable distribution workflows — **in progress**: shared UTM helper (`withUtm`), presets/snippets/QR on **My Polls** and **Home** post-create (chrome i18n’d), **Poll** owner “Sharing assets”; **native share** + **public poll URL** + **embed viewer URL** when a token exists; **OBS / browser-source** operator guide: [STREAMING-OBS-BROWSER-SOURCE.md](STREAMING-OBS-BROWSER-SOURCE.md) with in-app link (`docs.streamingObsBrowserSource`, optional build **`VITE_STREAMING_OBS_DOC_URL`**); **partial**: **My Polls** analytics + **Poll** owner metrics strings + UTC hour helpers (**`formatUtcWeekdayShort`**, **`formatUtcHourAtTopOfHour`**, **`myPolls.topCampaign`**, **`poll.metrics.*`**); **PollResults** overlay toolbar (**`poll.results*`**); next: richer in-page charts and other small UX passes.
3. **Trust layer**: anti-abuse scoring + moderation queue + rollback tools — **in progress**: env **IP** + **chat** burst quarantine (`TRUST_*_BURST_*`), combined **`quarantine_reason`** codes, **`trust_risk_score`**, owner **`moderation_counters`** + **`integrity_panel`** tags, Poll/My Polls copy; **`GET /admin/status`** **`trustMetrics`** includes quarantine rollups, **account-linked signals** (**`votes_account_linked_last_24h`**, **`votes_anonymous_last_24h`**, **`quarantine_pending_account_linked`**) for operator dashboards; next: deeper account-trust rules, **retention policies** (TTL / auto-delete).
4. **Eligibility layer**: extend identity tiers (e.g. platform-linked) with opt-in policy/consent UX — **partial**: **`home.voteEligibility.accountConsentNote`** when signed-in-only voting is selected or active on **Home** (create), **My Polls** (draft edit), and **Poll** owner “Sharing assets” (same string).
5. **Gamification (phased)**: ship **lightweight** items first (milestones, energy meters, cosmetic badges) behind poll flags; then **quests / drops / leaderboards** once identity + trust signals exist; reserve **provider-linked** or **paid-visibility** mechanics for later tiers and legal review.

---

## Implementation notes (for contributors)

- Prefer extending **`@asking-ng/contracts`** for any new wire shapes (phases, mod actions, analytics events).
- Upcoming poll formats (**ranked choice**, **rating scale**, **quiz**, **free-text**) can align with the reserved enum **`pollFormatExtensionSchema`** in `@asking-ng/contracts/poll` until vote/create APIs consume it.
- Large or risky integrations (platform OAuth, webhooks) should stay **off by default** and be documented in `stack.env.example` with clear security notes.
- **Distribution UX**: keep UTM campaign names and snippet text consistent between `MyPolls.tsx`, `Home.tsx` (post-create), and `Poll.tsx` (owner share block); prefer `shareUrlForPoll` / `shareUrlForPollResults` + `withUtm` over ad-hoc query strings; keep **public poll link**, **Web Share**, and **`apiUrl('poll/…/embed')` + `embed_token`** aligned across **My Polls**, **Poll** owner details, and **Home** “Access tokens & secrets” when a fresh embed token exists.
- **UTC weekday (`peak_dow_utc`):** format with **`client/src/lib/formatUtcWeekdayShort.ts`** + **`useLocaleTag()`** so list/metrics/dashboard stay consistent; avoid hard-coded English `Sun`–`Sat` arrays.
- **UTC clock hour (`peak_hour_utc`, hourly buckets 0–23):** format with **`client/src/lib/formatUtcHourAtTopOfHour.ts`** + **`useLocaleTag()`** (short timezone name via `Intl`); avoid concatenating a literal ` UTC` after hand-built `HH:00`.
- **Moderation queue copy:** keep new strings and key reuse aligned with **Shipped creator-facing UX** (Commercial packaging)—do not duplicate that list here.
- **Trust stack**: keep burst thresholds in **`lib/trustStackSignals.ts`** (single source) for **`trust_ip_burst`** / **`trust_chat_burst`** owner fields and **`trustStackSafeguardTags()`** on **`integrity_panel`**; vote path uses **`reasonFromTrustSignals`** + **`trustRiskScore`** in `voteOnPoll.service.ts`.
