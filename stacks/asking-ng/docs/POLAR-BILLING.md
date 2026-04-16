# Polar billing (hosted asking-ng)

**Polar** ([polar.sh](https://polar.sh/)) is the **default** payment and subscription surface for hosted SMB workspaces: checkout, renewals, and customer portal with less integration surface than raw Stripe Billing.

This doc is the **implementation handoff** for engineers. Product caps and tiers remain in [MONETIZATION-AND-PACKAGING.md](MONETIZATION-AND-PACKAGING.md).

---

## What Polar owns vs what asking-ng owns

| Concern | Owner |
|---|---|
| Card charge, receipt, basic subscription lifecycle | Polar |
| `workspaces.billing_plan` (default workspace per owner user) + mirrored `users.billing_plan` + usage limits + feature flags | asking-ng (Polar webhooks + reconcile update the workspace; owner user row kept in sync) |
| Metered overage (votes/month, WS seats) | asking-ng meters + billing policy (Polar may invoice fixed add-ons; true-up may be internal or contact-sales) |
| Enterprise quotes, custom caps, regulated Tracks A/D | asking-ng **contact sales** + separate contract (Polar optional or absent) |

---

## Environment variables (API)

| Variable | Required when | Purpose |
|---|---|---|
| `ENABLE_POLAR_WEBHOOKS` | Receiving Polar webhooks | `true` to expose the webhook route; omit/false in OSS-only deploys. |
| `POLAR_WEBHOOK_SECRET` | `ENABLE_POLAR_WEBHOOKS=true` | Secret from Polar dashboard for the webhook endpoint; used to verify signatures. |
| `POLAR_CUSTOMER_PORTAL_URL` | Optional | HTTPS URL for **Manage subscription** (returned on `GET /profile/billing`). |
| `POLAR_CHECKOUT_CLOUD_TEAM_URL` | Optional | HTTPS checkout link for **cloud-team** tier. |
| `POLAR_CHECKOUT_CLOUD_PRO_URL` | Optional | HTTPS checkout link for **cloud-pro** tier. |
| `POLAR_PRODUCT_ID_CLOUD_TEAM` | Optional until SKUs exist | Polar **`product_id`** string for the Team product; used to map subscription webhooks to `billing_plan=cloud-team`. |
| `POLAR_PRODUCT_ID_CLOUD_PRO` | Optional until SKUs exist | Polar **`product_id`** for Pro → `billing_plan=cloud-pro`. |
| `POLAR_ACCESS_TOKEN` | Optional | **Organization access token** for Polar’s HTTP API (`subscriptions:read`). Enables **`POST /admin/billing/reconcile-polar`** to fetch each workspace `polar_subscription_id` and repair **`workspaces.billing_plan`** (and mirror) when webhooks lag or fail. |
| `POLAR_SERVER` | Optional | `production` (default) or `sandbox` — must match the tenant where subscriptions live. |

Wired in **`stack.env.example`** and **`api/src/lib/env.ts`**; webhook handler: **`POST /billing/webhooks/polar`** (see `api/src/server/billing.ts`). Idempotent receipts in table **`polar_webhook_deliveries`** (`webhook_id` = Standard `webhook-id` header, or `sha256:` body hash fallback).

**Checkout / portal URLs for the SPA:** set **`POLAR_CUSTOMER_PORTAL_URL`**, **`POLAR_CHECKOUT_CLOUD_TEAM_URL`**, **`POLAR_CHECKOUT_CLOUD_PRO_URL`** — exposed to logged-in users as **`GET /profile/billing`** (with **`billing.plan`** from the database) and surfaced on the **Developer** page for signed-in users (Polar links only when URLs are non-empty).

---

## Webhook endpoint (implemented)

- **Path:** `POST /billing/webhooks/polar` (public URL often `/api/billing/webhooks/polar` when Caddy uses `handle_path /api/*`).
- **Discovery:** `GET /billing/webhooks/info` when `ENABLE_POLAR_WEBHOOKS=true` (returns `deliveriesStoredCount` and optional `lastStoredDelivery` `{ eventType, receivedAt }` from **`polar_webhook_deliveries`** for ops dashboards).
- **Body:** verified as **raw bytes** (Standard Webhooks); the API uses a scoped Fastify JSON parser so the body stays a `Buffer` for `validateEvent`.
- **Verification (TypeScript):** `@polar-sh/sdk/webhooks` — `validateEvent(body, headers, POLAR_WEBHOOK_SECRET)`.
- **Idempotency:** insert into **`polar_webhook_deliveries`** keyed by **`webhook-id`** (or body-hash fallback); duplicate deliveries return **204** without re-running entitlement logic (avoids double-applying the same delivery).
- **Entitlements:** after a **new** delivery row is stored, the API runs **`applyPolarSubscriptionWebhookEvent`** for `subscription.*` events (see `api/src/lib/polarSubscriptionApply.ts`): resolves the billing **`workspaces`** row (metadata **`asking_ng_workspace_id`**, then **`asking_ng_user_id`** default workspace, then workspace Polar ids), updates **`workspaces.polar_*`** + **`workspaces.billing_plan`**, and mirrors onto the owner **`users`** row. Failures are logged but still return **204** so Polar does not wedge retries.
- **Failure handling:** invalid signature → **403**; misconfiguration (enabled, no secret) → **503**; verification success → **204** no body.

Polar docs: [Webhooks delivery](https://docs.polar.sh/integrate/webhooks/delivery), [Setup webhooks](https://docs.polar.sh/developers/webhooks).

---

## Product → `billing_plan` mapping

Create **one Polar product or price per** commercial plan or add-on (naming should match [MONETIZATION-AND-PACKAGING.md](MONETIZATION-AND-PACKAGING.md)):

| Internal plan | Example Polar products |
|---|---|
| `cloud-team` | Single monthly + annual price for team tier |
| `cloud-pro` | Single monthly + annual price for pro tier |
| Add-ons | One subscription item per add-on pack (or bundled products if Polar supports your layout) |

Configure **`POLAR_PRODUCT_ID_CLOUD_TEAM`** and **`POLAR_PRODUCT_ID_CLOUD_PRO`** to the Polar **`product_id`** values emitted on subscription payloads. The webhook handler maps **`subscription.active`**, **`subscription.updated`**, **`subscription.uncanceled`**, **`subscription.canceled`**, and **`subscription.revoked`** to **`workspaces.billing_plan`** (and mirrors **`users.billing_plan`**) (`free` \| `cloud-team` \| `cloud-pro`): paid access is kept for **`active`**, **`trialing`**, and **`past_due`**; **`subscription.revoked`** never grants a paid plan.

**Linking checkout:** set **metadata** **`asking_ng_user_id`** to the numeric **`users.id`** (default workspace is created on signup / first use). Optionally set **`asking_ng_workspace_id`** to a specific **`workspaces.id`**. Otherwise the resolver matches **`workspaces.polar_subscription_id`**, then **`workspaces.polar_customer_id`** (mirrors stay aligned on the owner user).

On `subscription.canceled` / `invoice.payment_failed`, apply the **grace** and **downgrade** rules from [MONETIZATION-AND-PACKAGING.md](MONETIZATION-AND-PACKAGING.md) and [OPERATIONS.md](OPERATIONS.md) (today: non-paid subscription statuses set **`billing_plan`** back to **`free`**).

---

## Frontend

- **Developer** page (`/developer`): when the user is logged in, **`GET /profile/billing`** returns **`billing.plan`** (from the database) and, when configured, Polar portal / checkout links.
- **Plan state** is server-authoritative on the default **`workspaces.billing_plan`** (exposed via profile/billing the same as before); checkout URLs remain env-driven.

---

## Enterprise fallback

When a customer exceeds hosted self-serve limits or needs regulated modules, **stop** trying to express the deal in Polar; use **manual invoicing** or a procurement-friendly processor (**Stripe Billing**, **Paddle**, etc.) and store `enterprise-custom` entitlements administratively until a dedicated billing integration exists.

---

## Resilience, ownership, and reconstruction

**asking-ng should own enough state to survive Polar UI outages or a future provider change:**

| Artifact | Store in your DB / ops systems |
|---|---|
| Polar `customer_id`, `subscription_id` | **`workspaces.polar_*`** (mirrored on **`users`**) |
| Effective `billing_plan` + add-on flags | **`workspaces`** (+ mirror); **Polar is authoritative for money**, your DB is authoritative for **runtime** after each verified webhook |
| Webhook delivery audit | `polar_webhook_deliveries` (idempotency + forensic replay) |

**Reconstruction playbook (outline):**

1. Export or query Polar dashboard / API periodically for subscription list (ops backup), or rely on DB + webhook DLQ replay.
2. If webhooks were down: replay from Polar’s delivery history or call **`POST /admin/billing/reconcile-polar`** with **`POLAR_ACCESS_TOKEN`** set (optional JSON body `{ "dryRun": true, "limit": 50 }` to preview drift). The handler walks **`workspaces`** with non-empty **`polar_subscription_id`**, calls Polar **`subscriptions.get`**, and applies the same entitlement rules as webhooks. **`dryRun: true`** reports drift without writing the DB.
3. If changing billing vendor: freeze plan **upgrades** until dual-write or one-time migration maps old IDs → new processor; keep `billing_plan` enum stable.

**Runtime during Polar outage:** customers may be unable to open checkout or portal; existing sessions should keep working on **cached** `billing_plan` until grace policies in [MONETIZATION-AND-PACKAGING.md](MONETIZATION-AND-PACKAGING.md) / [OPERATIONS.md](OPERATIONS.md) apply. Do not silently expand paid entitlements on “assume still paid” without a reconciliation timestamp policy.

---

## Merchant of record, tax, and invoices (hosted)

- **Polar’s role** for SMB checkout typically includes **payment collection**; **VAT/GST display and invoicing rules** follow Polar’s current product behavior and your business entity registration—**verify at launch** against Polar docs and your accountant.
- **Enterprise / Paddle / Stripe Billing:** when **Paddle** (or similar) is merchant of record, tax and invoice branding differ from Polar-only—document which path a customer is on in support runbooks.
- Publish **subprocessors**, **billing contact**, and **invoice data** in legal pages as required for B2B procurement.

---

## Dunning, chargebacks, and mid-cycle changes (SaaS, non-gambling)

| Situation | Default posture (tune in ToS) |
|---|---|
| **Failed renewal / `past_due`** | Keep paid access during grace (~7 days per monetization spec); banner + portal link; then downgrade to `free` if still unpaid. |
| **Mid-cycle add-on remove** | Entitlement drops at end of paid period unless proration policy says otherwise; UI warns before removal. |
| **Card chargeback (SaaS)** | After processor notification, mark account for review; may revoke paid entitlements **after** dispute window per processor rules; log in billing audit trail. |
| **Refund requests** | Follow published Refund Policy; reconcile entitlements immediately on refund if access must end. |
| **Partial payment / incomplete checkout** | Do not grant paid entitlements until Polar confirms **paid** / **trialing** per webhook; treat abandoned checkouts as `free`. |
| **Proration / mid-cycle upgrade** | If Polar emits prorated charges, keep **internal ledger rows** aligned to invoice line items for support disputes. |

Tracks **A/D** (regulated) need **separate** chargeback and customer-funds playbooks—do not reuse SaaS defaults.

### Currency (non-USD)

v1 price book is **USD**. If you add **other settlement currencies**, confirm Polar (or alternate processor) **payout and tax** behavior, update displayed prices and **refund policy**, and keep **`billing_plan`** independent of currency (plan is logical tier; invoice currency is billing metadata).

---

## Entitlement scope (v1)

**Source of truth:** **`workspaces.billing_plan`** on each user’s **default workspace** (one workspace per owner today, unique on `owner_user_id`). **`users.billing_plan`** is kept in sync for API compatibility and older readers. Product docs may still say **`workspace_plan`** — that maps to the default workspace’s **`billing_plan`**. Multi-workspace (several billable workspaces per account) is a later schema + checkout metadata extension beyond **`asking_ng_workspace_id`**.

---

## Observability (reconcile + drift)

Structured logs (search in Loki or your log stack):

| `event` | Meaning |
|---|---|
| `polar.reconcile.plan_drift` | Polar API snapshot would change **`billing_plan`** vs DB for a user (warning). |
| `polar.reconcile.fetch_failed` | `subscriptions.get` failed for a stored workspace subscription id. |
| `polar.reconcile.summary` | End-of-run counts: `scanned`, `polar_fetch_errors`, `drift_detected`, `rows_updated`, `dry_run`. |
| `polar.reconcile.route_error` | Admin handler caught an exception. |

**Prometheus:** `observeIntegrationEvent('polar_reconcile_drift')` increments **`asking_ng_integrations_events_total`** with label **`event=polar_reconcile_drift`** (once per reconcile run if any drift rows). Suggested alerts: sustained **`polar.reconcile.plan_drift`** after a scheduled reconcile, or repeated **`polar.reconcile.fetch_failed`** (bad token, deleted subscription ids, or network).

---

## Related

- [OSS-AND-COMMERCIAL-POSITIONING.md](OSS-AND-COMMERCIAL-POSITIONING.md) — narrative for OSS vs hosted
- [MONETIZATION-AND-PACKAGING.md](MONETIZATION-AND-PACKAGING.md) — grace, limits, migration stance
