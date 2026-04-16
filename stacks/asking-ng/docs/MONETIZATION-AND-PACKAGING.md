# Monetization and packaging (roadmap spec)

This document is the **repo-local** packaging and commercial roadmap for asking-ng: OSS vs hosted tiers, hard limits, add-ons, billing/metering semantics, and regulated optional modules. **Engineering and legal review still apply** before any production billing or wagering/markets ship.

**Related:** [CREATOR-STREAMER-ROADMAP.md](CREATOR-STREAMER-ROADMAP.md) (product backlog; **Shipped creator-facing UX** there is the canonical list of limit/trust-related UI already in the app), [OSS-AND-COMMERCIAL-POSITIONING.md](OSS-AND-COMMERCIAL-POSITIONING.md) (OSS vs paid narrative + contribution boundary), [POLAR-BILLING.md](POLAR-BILLING.md) (hosted billing + webhooks), [OPERATIONS.md](OPERATIONS.md) (runtime + entitlement failure modes), [API-REFERENCE.md](API-REFERENCE.md) (planned limit error codes).

---

## Plan identifiers

| Identifier | Meaning |
|---|---|
| `free` | OSS / default self-host; adoption-focused core |
| `cloud-team` | Hosted flat tier (team scale) |
| `cloud-pro` | Hosted flat tier (higher caps + premium tooling) |
| `selfhost-pro` | Paid license unlock for advanced modules on self-host |
| `enterprise-custom` | Quote-based limits, compliance, SLA, regulated modules |

---

## Tier boundaries (summary)

| Dimension | `free` | `cloud-team` | `cloud-pro` | `selfhost-pro` | `enterprise-custom` |
|---|---|---|---|---|---|
| Seats | n/a (OSS) | Unlimited | Unlimited | Per deployment policy | Contract |
| Core poll lifecycle | Yes | Yes | Yes | Yes | Yes |
| Basic moderation | Yes | Yes | Yes | Yes | Yes |
| Quarantine automation rules | No | Limited presets | Full | Full | Contract |
| Anti-abuse tuning | Baseline | Limited | Advanced | Advanced | Contract |
| Audit / forensic timelines | Short / none | Basic / medium retention | Full + long retention | Configurable | Contract |
| Campaign attribution | Top-level | Dashboard + trends | Cohort / segments | Cohort / segments | Contract |
| Ops dashboards / alert packs | Docs-only DIY | Managed templates | + premium packs | Premium package | Contract |
| Usage scale (events, WS, storage) | Baseline caps | Higher + add-ons | Highest + lower overage | License + optional support | Committed blocks |
| Track A (real-money wagering) | No | No | No | Default no | Yes after licensing |
| Track D (event contracts) | No | No | No | Default no | Yes after licensing |
| Track B (non-wager predictions) | No / gated beta | Gated beta | Gated beta | Operator opt-in | Contract |
| Track C (virtual / loyalty currency) | No | Single provider, limited | Multi-provider + analytics | Operator opt-in + ToS ack | Intake if beyond tier |
| Gamification & retention (non-wager; badges, streaks, meters, quests, opt-in leaderboards) | Baseline UX | Templates + quests / drops | Leaderboards at scale + funnel analytics | License unlock for advanced packs | Contract |

---

## Hard numeric limits (v1 draft)

**Beyond limits:** surfaces “Need higher limits? Contact sales” at usage meters, warning emails (80%, 95%, 100%), and hard-limit API responses. **Auto-qualify for enterprise** when projected monthly votes exceed 10M, WS concurrency exceeds 15k, active polls exceed 2k, or retention exceeds 365 days (indicative; final metering TBD).

| Limit | `free` | `cloud-team` | `cloud-pro` | `selfhost-pro` |
|---|---:|---:|---:|---|
| Active polls / workspace | 20 | 250 | 2000 | Default 2000 (configurable) |
| Votes per month | 50,000 | 1,000,000 | 10,000,000 | Infra-bound |
| WS concurrent subscribers (peak) | 100 | 2,000 | 15,000 | Capacity-tested guidance |
| Audit log retention | 14 d | 90 d | 365 d | Up to 1095 d by policy |
| Moderation history retention | 30 d | 180 d | 730 d | Configurable |
| Automation rules | 0 | 5 | 50 | 50 (license expandable) |
| Campaign attribution queries / day | 100 | 5,000 | 50,000 | Configurable |
| Data export jobs / day | 3 | 25 | 200 | Configurable |

**Track A / D / C operational defaults** for enterprise and paid-tier caps are in [Betting and markets](#betting-and-markets-four-tracks-default-posture) below; update them here whenever product or counsel changes delivery scope.

---

## API rate and WebSocket fanout (v1 draft)

**Intent:** “Unlimited seats” must not imply unlimited integrator abuse. These caps sit **beside** vote/month and WS **subscriber** limits in [Hard numeric limits](#hard-numeric-limits-v1-draft). Numbers are **draft**—validate under load before locking; self-host continues to use global env tunables in [OPERATIONS.md](OPERATIONS.md) until per-tier routing exists.

| Guardrail | `free` | `cloud-team` | `cloud-pro` | `selfhost-pro` | Notes |
|---|---:|---:|---:|---|---|
| Authenticated REST **sustained** req/min per user (default) | 120 | 600 | 3,000 | Deployment policy | Burst allowance ~2× sustained for short windows; stricter on anonymous vote surfaces |
| Poll WebSocket **server→client** update burst per poll | 30/s | 200/s | 1,500/s | Capacity-tested | Coalesce tick payloads where possible; shed with `USAGE_LIMIT_WS_FANOUT` + CTA |
| Outbound integration webhooks **delivery attempts** / min per workspace | 30 | 300 | 2,000 | Configurable | Protects partner endpoints and your own ops COGS |

Enforcement surfaces: HTTP `429` / planned `USAGE_LIMIT_API_RATE`; WebSocket close or server message with stable codes per [API-REFERENCE.md](API-REFERENCE.md).

---

## A-la-carte add-ons (v1, max 7 active per workspace)

| Add-on | Unlocks | Price target (USD/mo) | Eligible base plans |
|---|---|---:|---|
| Realtime Burst Pack | +10,000 concurrent WS subscribers | 29 | `cloud-team`, `cloud-pro` |
| Event Volume Pack | +2,000,000 votes/events per month | 19 | `cloud-team`, `cloud-pro` |
| Extended Retention Pack | +365 d audit + moderation history | 15 | `cloud-team` (included in `cloud-pro`) |
| Moderation Automation Pack | +25 rules + advanced actions | 25 | `cloud-team`, `selfhost-pro` |
| Compliance Export Pack | Signed bundles, schedules, immutable manifests | 39 | `cloud-team`, `cloud-pro`, `selfhost-pro` |
| Priority Support Pack | Response SLO targets + incident assist | 99 | `cloud-team`, `cloud-pro`, `selfhost-pro` |
| Social Currency Connectors Pack | +3 Track C provider connections | 19 | `cloud-team`, `cloud-pro` |

**Guardrails:** add-ons prorate monthly; workspace-level **spending cap** default on; no add-ons that remove core vote integrity or basic moderation safety from `free`.

---

## Pricing sheet (locked v1 hypothesis)

- **Currency:** USD. **Billing:** monthly and annual (annual ≈ 2 months free). **Model:** per workspace, unlimited seats.

**Scenario A (conversion-focused):** `cloud-team` $19/mo ($190/yr), `cloud-pro` $79/mo ($790/yr), `selfhost-pro` $39/mo ($390/yr).

**Scenario B (ARPU-focused):** `cloud-team` $29/mo ($290/yr), `cloud-pro` $99/mo ($990/yr), `selfhost-pro` $59/mo ($590/yr).

**Overage (cloud):** +$0.30 per additional 100k votes/events; +$5 per additional 100 GB/month retention envelope; warn 80%/95%; hard block typically 110% unless auto-overage enabled.

**Contact sales (`enterprise-custom`):** base platform fee from **$299/mo** (or $2,990/yr) + committed usage blocks + optional SLA/support; min term 3 mo monthly or 12 mo annual; quote from price book with **margin floor**; sub-floor deals need explicit approval.

**Trials / grandfathering:** 14-day trial (card optional for first cohort); **90-day** grandfathering window when existing capabilities move tiers.

**A/B (6 weeks):** primary = paid conversion from active mod-team workspaces; secondaries = 60d retention proxy, ARPU, add-on attach. **Winner:** higher LTV proxy unless conversion drops by more than 25% vs baseline; if within 10%, prefer lower support-ticket scenario.

---

## Premium bundles mapped to mod teams

| Bundle | What it sells |
|---|---|
| Trust & safety | Risk controls, quarantine automation, wave actions, incident playbooks, forensic views |
| Ops & reliability | SLO dashboards, alert presets, backup/recovery UX, retention policies |
| Team workflow | Role templates, approvals, collaborator permissions, action history / replay |
| Streamer engagement (Track C) | Loyalty-currency markets, overlays, mod tooling, provider-respecting settlement |
| Gamification & retention (non-wager) | Milestones, streaks, cosmetic badges, crowd “energy” meters, quests/drops, opt-in leaderboards, quiz play-along; default **no transferable value** (Track B–style); higher limits / automation on paid tiers if metered |
| Brand / creator (later) | Themes, domains, embed customization |

---

## Converting existing product into tiers (phased)

1. **Phase 1 (low risk):** retention tiers, managed dashboard packs, richer attribution.
2. **Phase 2:** anti-abuse tuning + moderation automation presets.
3. **Phase 3:** forensic replay/diff + advanced approvals.
4. **Phase 4 (optional, parallel where safe):** non-wager **gamification** (milestones → quests / drops → leaderboards); keep core participation free-friendly; meter heavy read/automation on paid tiers per [CREATOR-STREAMER-ROADMAP.md](CREATOR-STREAMER-ROADMAP.md).

**Keep free:** core create/read/vote, basic moderation, basic exports, baseline realtime.

**Do not** abruptly remove relied-on behavior; use in-app migration notices + grandfathering.

---

## Entitlement checks, errors, and degraded behavior

| Layer | Rule |
|---|---|
| API | Authoritative enforcement on all mutating paths (polls, votes, exports, webhooks, automation). |
| API (partial, shipped) | `POST /poll` and **`POST /poll/:id/clone`**: when **`BILLING_ENFORCE_LIMITS=true`**, reject if non-archived owned polls ≥ cap for `users.billing_plan` (**`USAGE_LIMIT_ACTIVE_POLLS`**, HTTP **403**; details include `max`, `current`, `plan`). **`PUT /poll/:id/vote`**: same flag rejects when new vote **rows** would push the poll **owner’s** non-quarantined vote count for the **UTC calendar month** over the plan cap (**`USAGE_LIMIT_VOTES`**, HTTP **403**; details include `max`, `current`, `plan`, `incoming`). **`GET /poll/:id/export`** and **`GET /profile/export`**: same flag rejects when completed export jobs for the **workspace** (poll **owner** `creator_user_id`, or signed-in user for profile export) in the **UTC calendar day** ≥ plan cap (**`USAGE_LIMIT_EXPORTS`**, HTTP **403**; details `max`, `current`, `plan`). Metering rows: `audit_logs.action=usage.data_export` with `details.workspace_user_id`. **`GET /profile/billing`** **`usage`** adds `exportsToday`, `maxExportsPerDay` plus prior fields. Default **off**. Caps in `api/src/lib/billingLimits.ts`; checks in `api/src/lib/billingPollQuota.ts`, `api/src/lib/billingVoteQuota.ts`, `api/src/lib/billingExportQuota.ts`; vote count SQL in `api/src/controller/poll/voteOnPoll.repository.ts`. |
| WebSocket edge (partial, shipped) | **`GET /ws/poll/:id`**: room size capped by **`min(WS_MAX_SUBSCRIBERS_PER_POLL, plan tier)`** when **`BILLING_ENFORCE_LIMITS=true`** (orphan polls → `free` tier); otherwise env cap only. Rejects with WebSocket close **1008** and reason **`USAGE_LIMIT_WS_SUBSCRIBERS`**. Resolver in `api/src/lib/billingWsQuota.ts`. **Outbound fanout**: `notifyPollLive` **update** payloads are shed when per-poll server→client rate exceeds **`min(WS_FANOUT_MAX_PER_POLL_PER_SEC, plan tier)`** / s (UTC-ish 1s window); **`panic`** / **`deleted`** are not shed. Structured log `poll.live.ws_fanout_shed` with **`USAGE_LIMIT_WS_FANOUT`**. Implementation in `api/src/lib/billingWsFanout.ts`. |
| Usage warnings (partial, shipped) | **`GET /profile/billing`** includes optional **`usage.warnings`** when any meter is ≥ **80%** or ≥ **95%** of its cap (`activePolls`, `votesThisMonth`, `dataExports` — values **`80`** / **`95`** for UI). Does not block traffic. Builder in `api/src/lib/billingUsageWarnings.ts`. Client: severity banner on **Home**, **My Polls**, and **Developer** (`billing.usageNearLimit80` / `billing.usageNearLimit95`); Developer also lists per-meter hints. **Poll** page: localized hint when the live WebSocket closes with **`1008`** / **`USAGE_LIMIT_WS_SUBSCRIBERS`** (room cap). |
| UI | Mirrors limits; never sole enforcement. |
| Regulated modules | No shadow endpoints; Tracks A/D/C only through dedicated gated APIs with jurisdiction / provider checks. |

**Recommended error families** (stable codes for clients): `PLAN_LIMIT_*` (entitlement missing), `USAGE_LIMIT_*` (numeric cap), optional `BILLING_*` (payment / grace). Use HTTP `402` or `403` vs `429` consistently per product decision; document final mapping in [API-REFERENCE.md](API-REFERENCE.md) when implemented.

**Degraded modes:**

| Condition | Behavior |
|---|---|
| Payment failed (in grace) | Banner + read-mostly; block only tier-expanding mutations if needed |
| Payment hard fail | Downgrade to `free` caps after notice; preserve export windows |
| Self-host license expired | Configurable offline grace (~72h default), then disable premium modules only |
| Webhook / billing drift | Alert ops; prefer fail-closed for *new* premium usage until reconciled |

---

## Billing platform (implementation checklist)

| Topic | Decision / action |
|---|---|
| Provider (hosted) | **Default: [Polar](https://polar.sh/)** for SMB hosted checkout + subscriptions + portal; map Polar products to **`workspaces.billing_plan`** on the owner’s default workspace (mirrored on **`users.billing_plan`**; see [POLAR-BILLING.md](POLAR-BILLING.md)). |
| Provider (enterprise) | **Parallel path**: manual invoice, **Paddle** (MoR), or **Stripe Billing** when procurement, custom limits, or regulated modules require it—do not force Polar to cover enterprise alone. |
| Webhooks | Polar uses [Standard Webhooks](https://www.standardwebhooks.com/); verify with `@polar-sh/sdk` `validateEvent` + `POLAR_WEBHOOK_SECRET`; idempotent handlers; DLQ + replay; alert on drift vs internal entitlements. |
| Failed payment | Grace ~7 days; define read-only vs hard-disable; email + in-app copy. |
| Self-host license | Issuance, rotation, offline grace, revocation audit trail (orthogonal to Polar; license key or separate seller). |

---

## Metering and disputes

| Topic | Spec |
|---|---|
| Billable events | Define vote/event counting, idempotency keys, retries, admin actions excluded/included. |
| Tracks A / D / C | Meter stake/notional, fees, voids, chargebacks (A); orders/trades/OI/liquidations/resolutions (D); point escrow + provider quota (C). |
| Time | UTC monthly reset; proration on mid-cycle upgrades. |
| Customer visibility | Daily rollups + exportable usage ledger. |
| Disputes | First response SLA (e.g. 2 business days), correction ledger entries, partial credit policy. |

### Meter integrity (anti-gaming)

- **Idempotent votes:** same client submission retries must not multiply billable vote counts (stable idempotency keys per ballot attempt).
- **Admin and mod actions:** exclude from “vote” meters unless product explicitly sells metered admin events.
- **Synthetic / abusive traffic:** velocity anomalies, single-IP fanout across many identities, and integrator loops feed **trust & safety** and may **throttle or block** without counting as paid overage; repeated abuse → account action + sales review for enterprise carve-outs.
- **COGS alignment:** very large workspaces inflate logs, traces, and support load—either cap included observability, reflect in support packs, or model in margin.

---

## Legal, tax, procurement (high level)

Publish ToS, Privacy, AUP, Refund, plan-change + grandfathering policies. B2B: invoices, VAT/GST strategy, DPA/SCC, subprocessors, residency stance. Segregate **product data** vs **billing meter data** retention. Tracks A/D/C: counsel-led licensing, age/geo, AML where required, gambling payments + chargeback playbooks, platform developer rules for Track C, kill switches per provider. **Youth-heavy audiences:** align copy and data collection with platform norms and counsel (even without real-money tracks). **Accessibility:** paid admin and billing flows should meet a baseline suitable for team procurement (WCAG-oriented targets as you mature).

### Erasure vs immutable audit / compliance artifacts

Subject to counsel and jurisdiction:

| Data class | Typical posture |
|---|---|
| End-user profile / PII | Honor deletion/export requests; remove or irreversibly anonymize direct identifiers where required. |
| Operational audit logs | May retain **redacted** or **hashed** references to satisfy security investigations; minimum necessary. |
| **Immutable export manifests** / signed compliance bundles | Often **cannot** be silently rewritten; deletion may mean **append-only revocation records** + new manifest generation rather than mutating history. |
| Billing and metering ledgers | Retain for tax/accounting statutory periods; separate from product DB where practical. |

**Product rule of thumb:** user-facing “delete my account” completes for **interactive product data** first; compliance artifacts transition to **legal hold / tombstone** states rather than silent hard-delete when the ledger is evidential.

---

## Success metrics (implementation guardrails)

Beyond conversion and ARPU experiments, track:

| Metric | Why |
|---|---|
| Time-to-first-paid-value | e.g. first saved automation rule or first compliance export—proves onboarding, not just checkout. |
| Moderation false-positive rate by tier | Quality signal for trust/safety upsell. |
| Support tickets per $1 ARR (and per active workspace) | Pricing A/B guardrail; operational health. |

---

## Support operations

| Tier | Posture |
|---|---|
| Free / OSS | Community channels |
| Paid cloud | Email support; SLOs only where sold |
| Priority Support Pack | Contracted response targets + incident assist |
| Enterprise | Custom matrix + templates for incidents and entitlement rollback |

---

## Migration, churn, and sales ops

- **Downgrade simulator** before limits bite; scheduled export reminders.
- **Burst credits** (optional, e.g. quarterly) for good-faith small overages on `cloud-team`.
- **Reactivation** time-boxed offers after failed payment or downgrade.
- **Enterprise intake:** peak concurrency, monthly events, retention, compliance, integrations, uptime; add Track A/D/C annexes per betting / legal sections in this doc and counsel checklists.
- **Quote calculator** from price book + committed blocks; **red lines:** unlimited liability, uncapped flat usage without commit, custom SLA without fee.

### Multi-workspace and agencies (v1 stance)

- **v1 self-serve:** one **billing subscription** maps to one **workspace** (or one primary workspace per customer account—match your auth model). No consolidated “org invoice” across many workspaces in Polar-only v1.
- **Agencies / MCNs** managing many channels: either **multiple subscriptions** (operational overhead on them) or **`enterprise-custom`** for pooled usage, single invoice, and committed blocks.

### Self-host ↔ hosted migration (v1 stance)

- **Primary path:** **export-first**—use existing export jobs + documented Postgres backup/restore for operators who control both sides.
- **No promise** of one-click import from arbitrary self-host DB into multi-tenant hosted without engineering review (schema drift, secrets, PII).
- **Assisted migration** is an **enterprise** or paid onboarding SKU if you offer it; document support expectations in ToS.

### Sandbox / staging workspaces

- Non-production workspaces should either use **`free`** caps, a dedicated **`sandbox`** flag (no billing), or a **fixed low meter** so load tests do not pollute production usage or invoices.
- Clearly separate **API keys** for staging vs production in docs and UI.

### Downgrade and offboarding (cloud)

- **Before downgrade:** surface **export deadlines** and webhook URL changes; optional **read-only** window per failed-payment policy.
- **At downgrade:** revoke **premium-only API capabilities** and **add-on entitlements**; trim retention schedules to `free` tier; rotate or invalidate **integration secrets** if policy requires clean separation.
- **Voluntary churn:** offer **data export** + **portal link** until account deletion window closes; document how long **billing records** survive vs **product DB** (see **Erasure vs immutable audit** under Legal in this doc).

---

## Experiment hygiene

Pre-register primary metric, guardrails (support tickets / paid user, downgrade rate, payment failure rate), sample size, duration, **stop rules** if guardrails breach.

---

## Betting and markets (four tracks, default posture)

| Track | Scope | Default packaging |
|---|---|---|
| A | Real-money sportsbook-style | `enterprise-custom` only; licensed path; turnover rake on accepted stake; min monthly platform fee |
| B | Non-wager “show” predictions | Gated beta; strict no third-party value |
| C | Platform loyalty / virtual currency | Paid cloud differentiation; provider checks; no cash-out; no secondary market |
| D | Event contracts / prediction-market class | `enterprise-custom`; oracle governance, liquidity, surveillance, tax/accounting per plan hardening |

OSS boundary: keep settlement ledgers + risk engines for A/D **out of public OSS** if policy requires.

### Track D: initial liquidity (product decision)

Before listing tradable markets, choose **who supplies opening depth** so pilots do not stall or hide tail risk:

| Model | When to use |
|---|---|
| **Paused until depth** | Markets do not trade until minimum book size is met (creator, LPs, or venue seed). |
| **Partner / venue liquidity** | asking-ng is distribution + risk UX; regulated core on licensed venue. |
| **Operator-seeded house liquidity** | Only with explicit reserves, disclosures, and counsel approval—high operational and regulatory load. |

Default conservative posture for pilots: **no trading until explicit liquidity commitment** is recorded in runbooks.

### Kill-switch and provider incident drills

- **Track C:** per-provider disable is required in policy; **quarterly tabletop**: trigger kill-switch in staging, verify markets pause, overlays show status, comms template published, re-enable checklist signed.
- **Tracks A/D:** include payment/oracle/partner failure modes; align with [OPERATIONS.md](OPERATIONS.md) `INCIDENT_MODE` patterns where applicable.

### Sanctions, PEP, and high-risk identity (Tracks A–D)

- **Tracks A/D (cash or cash-like settlement):** sanctions screening, PEP workflows, and geo eligibility are **non-optional** where counsel mandates; align with enterprise intake.
- **Track C (non-cash points):** default posture is **platform ToS + abuse tooling** only; if the product ever bridges to **payouts**, **giftable value**, or **strong identity** beyond platform IDs, add **sanctions/PEP screening** and jurisdiction review with counsel (same pattern as Track A onboarding).

### Enterprise operational defaults (v1 draft)

Starting **policy numbers** for pilots; counsel and venue rules override.

**Track A (`enterprise-custom`):**

| Default | Value |
|---|---:|
| Open betting markets per workspace | 50 concurrent |
| Max liability per market (operator hard cap) | $25,000 notional (currency-specific) |
| Max open user positions per market | 10,000 tickets |
| Settlement SLA target | 24 h after official result source locks |
| Cooling-off after self-exclusion re-enable | 24 h minimum (jurisdiction-dependent) |

**Track D (`enterprise-custom`):**

| Default | Value |
|---|---:|
| Listed tradable markets per workspace | 200 active |
| Max open interest per market | 250,000 contracts |
| Max position per user per market | 25,000 contracts |
| Price tick size | 0.1¢ of contract payout notion (per listing) |
| Trading rate limit | 50,000 orders/min per workspace (burst) |
| Oracle resolution challenge window | 24 h default |

**Track C (paid cloud tier defaults):**

| Default | `cloud-team` | `cloud-pro` |
|---|---:|---:|
| Open markets per workspace | 25 concurrent | 200 concurrent |
| Provider connections | 1 | 5 |
| Max stake per bet (points) | 1,000,000 (hard cap; lower per policy) | same |
| Max total points escrowed per market | 250,000,000 | same |
| Max bets per minute per market | 5,000 (burst) | same |
| Optional virtual rake (if permitted) | 0.10%–1.00% of staked points per accepted bet (null sink; no creator cash-out) | same |

---

## Adjacent streamer features

Prioritized backlog themes (**gamification**, tips, sponsors, drops, quests, overlays, clip hooks, CRM-lite, team workspaces) live in [CREATOR-STREAMER-ROADMAP.md](CREATOR-STREAMER-ROADMAP.md); map each to a bundle + tier when scoping an epic.

---

## Plan hardening (markets / betting)

Operational checklist (liquidity, oracle governance, insider policy, geo/sanctions, brand safety, incident comms, partner exit, security, privacy vs transparency, reserves, surveillance, matching-engine SRE, margin, settlement finality, tax, accounting exports, law enforcement handling, UGC listing workflow, responsible UX): expand in this doc and runbooks as policies lock; use counsel-driven annexes rather than shipping implicit defaults.

---

## External references (categories)

- [lawn](https://lawn.video/) / [lawn GitHub](https://github.com/pingdotgg/lawn) — simple flat tiers
- [PostHog pricing](https://posthog.com/pricing?o=open-source) — usage + open-source funnel
- [Kalshi](https://kalshi.com/), [Polymarket](https://polymarket.com/) — reference UX for regulated / market-style products (not implementation commitments)
