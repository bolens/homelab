# asking-ng operations guide 🛠️

## Purpose

Operational reference for runtime topology, ingress flow, client build options, and admin role lifecycle.

## Use This When

- You are verifying traffic flow across Caddy, frontend, API, and Postgres.
- You need build-time client env behavior for deployments.
- You are handling admin bootstrap/role lifecycle questions.

## Related Docs

- [../README.md](../README.md)
- [API-REFERENCE.md](API-REFERENCE.md)
- [API-SLO-DASHBOARD-CHECKS.md](API-SLO-DASHBOARD-CHECKS.md)
- [CI-REPO-WORKFLOW.md](CI-REPO-WORKFLOW.md)
- [API-READ-MODEL-STRATEGY.md](API-READ-MODEL-STRATEGY.md)
- [BACKUP-RESTORE-RUNBOOK.md](BACKUP-RESTORE-RUNBOOK.md)
- [MONETIZATION-AND-PACKAGING.md](MONETIZATION-AND-PACKAGING.md)
- [OSS-AND-COMMERCIAL-POSITIONING.md](OSS-AND-COMMERCIAL-POSITIONING.md)
- [POLAR-BILLING.md](POLAR-BILLING.md)

## Quick Orientation

| Topic | Where to look |
|---|---|
| Upstream origin and project scope | [jdleo/asking](https://github.com/jdleo/asking) and this README |
| Future feature backlog | [CREATOR-STREAMER-ROADMAP.md](CREATOR-STREAMER-ROADMAP.md) |
| Backup/restore runbook | [BACKUP-RESTORE-RUNBOOK.md](BACKUP-RESTORE-RUNBOOK.md) |
| Packaging, limits, billing roadmap | [MONETIZATION-AND-PACKAGING.md](MONETIZATION-AND-PACKAGING.md) |
| Polar webhooks + checkout handoff | [POLAR-BILLING.md](POLAR-BILLING.md) |
| Polar links for logged-in users | `GET /profile/billing` (JWT) — see [POLAR-BILLING.md](POLAR-BILLING.md) |

## Plans, entitlements, and degraded behavior (hosted roadmap)

Homelab/OSS deployments today behave as **unlicensed full capability** unless you introduce plan flags. When hosted billing and `selfhost-pro` licenses exist, operators should treat **entitlements** as part of incident response:

| Concern | Operational expectation |
|---|---|
| Source of truth | Subscription / license service → replicated `workspace_plan` (or deployment license) in API; reconcile on a schedule. |
| Enforcement | API + websocket edge are authoritative; UI is advisory only. |
| Drift | If billing webhooks lag, prefer blocking **new** premium consumption over silent overage; page on reconciliation failure. |
| Grace | Failed payment: banner + time-boxed grace before hard downgrade; self-host: short offline grace before premium modules disable. |
| Billing provider outage | Polar checkout/portal may be unavailable while the API stays up; rely on **cached** `billing_plan` and the reconstruction notes in [POLAR-BILLING.md](POLAR-BILLING.md); communicate status on status page if you operate one. |
| Kill switches | Regulated and platform-sensitive modules (Tracks A–D, LLM, webhooks) should remain **env- and flag-gated** with runbooks (see existing `INCIDENT_MODE` patterns). |

### Billing and metering incidents (hosted)

| Situation | Ops response |
|---|---|
| Customer disputes a **usage meter** | Open **usage ledger** row + raw event idempotency keys; apply correction policy from [MONETIZATION-AND-PACKAGING.md](MONETIZATION-AND-PACKAGING.md) (disputes); avoid manual entitlement edits without billing audit note. |
| **Polar / portal** unavailable | Per [POLAR-BILLING.md](POLAR-BILLING.md): no new upgrades via checkout; rely on cached `billing_plan`; status page if you run one. |
| **Webhook drift** alert | Pause **new** premium entitlements until reconcile job or replay completes; see “Drift” in the table above. |

Error semantics and HTTP codes for plan limits will live in [API-REFERENCE.md](API-REFERENCE.md) once implemented.

## Traffic and Networking Model

```mermaid
flowchart LR
  Client[Browser Client]
  Caddy[Caddy]
  FE[asking-ng-frontend (caddy static)]
  API[asking-ng-api]
  DB[(asking-db / Postgres)]

  Client --> Caddy --> FE
  Caddy -->|/api/*| API --> DB
```

Request path summary: Client -> Caddy -> (`asking-ng-frontend` for SPA, `asking-ng-api` for `/api/*`) -> `asking-db`.

| Layer | Component | Purpose |
|---|---|---|
| Edge ingress | Caddy | Public entrypoint; enforces compression, security headers, and request-size limit (`1MB` on `/api/*`) |
| Web app | `asking-ng-frontend:80` | Serves SPA assets and history-fallback routing |
| API app | `asking-ng-api:3001` | Handles REST + WebSocket + admin/moderation logic |
| Database | `asking-db` | Internal-only Postgres (`asking_ng_pg_data` volume) |
| Local smoke access | `docker compose exec asking-api` | Default checks are internal-only; optional host loopback via `docker-compose.debug.yml` |

## Policy Ownership

To keep behavior predictable, request/response policy is intentionally split by layer:

| Concern | Owner | Where configured |
|---|---|---|
| Security headers (`X-Content-Type-Options`, `Referrer-Policy`, `X-Frame-Options`, `Permissions-Policy`) | Edge Caddy | `caddy_snippet.conf` (`asking_ng_edge_policy`) |
| Compression (`encode zstd gzip`) | Edge Caddy | `caddy_snippet.conf` (`asking_ng_edge_policy`) |
| API request body limit (`1MB` on `/api/*`) | Edge Caddy | `caddy_snippet.conf` (`asking_ng_site_routes`) |
| API path routing and forwarded headers | Edge Caddy | `caddy_snippet.conf` (`asking_ng_api_proxy`) |
| SPA static files and history fallback | Frontend Caddy | `client/Caddyfile` |

Operational rule: if a policy affects both SPA and API traffic, set it at edge Caddy; keep frontend Caddy focused on static file serving only.

## Alternate Edge Examples

If you run another edge proxy, keep the same contract:

- `/api/*` -> `asking-ng-api:3001` with `/api` stripped
- `client_max_body_size` equivalent set to `1MB` on API paths
- security headers and compression at the edge
- all other paths -> `asking-ng-frontend:80`

### Caddy (reference edge snippet)

This example mirrors `caddy_snippet.conf.template` and should be updated with that template when behavior changes.

```caddyfile
(asking_ng_edge_policy) {
	encode zstd gzip
	header {
		X-Content-Type-Options "nosniff"
		Referrer-Policy "strict-origin-when-cross-origin"
		X-Frame-Options "SAMEORIGIN"
		Permissions-Policy "accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()"
	}
}

(asking_ng_api_proxy) {
	reverse_proxy asking-ng-api:3001 {
		header_up X-Forwarded-Proto {scheme}
		header_up X-Forwarded-Host {host}
		header_up X-Forwarded-For {remote_host}
	}
}

(asking_ng_frontend_proxy) {
	reverse_proxy asking-ng-frontend:80 {
		header_up X-Forwarded-Proto {scheme}
		header_up X-Forwarded-Host {host}
		header_up X-Forwarded-For {remote_host}
	}
}

(asking_ng_site_routes) {
	handle /api/* {
		request_body {
			max_size 1MB
		}
		uri strip_prefix /api
		import asking_ng_api_proxy
	}
	handle {
		import asking_ng_frontend_proxy
	}
}

asking-ng.home, asking-ng.local {
	tls internal
	import asking_ng_edge_policy
	import asking_ng_site_routes
}

http://asking-ng.example.com {
	import asking_ng_edge_policy
	import asking_ng_site_routes
}

asking-ng.example.com {
	import asking_ng_edge_policy
	import asking_ng_site_routes
}
```

### Traefik (dynamic file example)

```yaml
http:
  middlewares:
    asking-ng-security:
      headers:
        contentTypeNosniff: true
        frameDeny: false
        customFrameOptionsValue: "SAMEORIGIN"
        referrerPolicy: "strict-origin-when-cross-origin"
        customResponseHeaders:
          Permissions-Policy: "accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()"
    asking-ng-api-strip:
      stripPrefix:
        prefixes:
          - /api
    asking-ng-api-limit:
      buffering:
        maxRequestBodyBytes: 1048576
    asking-ng-compress:
      compress: {}
  routers:
    asking-ng-api:
      rule: "Host(`asking-ng.example.com`) && PathPrefix(`/api/`)"
      service: asking-ng-api
      middlewares:
        - asking-ng-security
        - asking-ng-compress
        - asking-ng-api-limit
        - asking-ng-api-strip
    asking-ng-web:
      rule: "Host(`asking-ng.example.com`)"
      service: asking-ng-frontend
      middlewares:
        - asking-ng-security
        - asking-ng-compress
  services:
    asking-ng-api:
      loadBalancer:
        servers:
          - url: "http://asking-ng-api:3001"
    asking-ng-frontend:
      loadBalancer:
        servers:
          - url: "http://asking-ng-frontend:80"
```

### nginx (edge reverse proxy)

```nginx
server {
  listen 443 ssl;
  server_name asking-ng.example.com;

  gzip on;
  gzip_types text/plain text/css application/javascript application/json image/svg+xml;

  add_header X-Content-Type-Options "nosniff" always;
  add_header Referrer-Policy "strict-origin-when-cross-origin" always;
  add_header X-Frame-Options "SAMEORIGIN" always;
  add_header Permissions-Policy "accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()" always;

  location /api/ {
    client_max_body_size 1m;
    rewrite ^/api/(.*)$ /$1 break;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_pass http://asking-ng-api:3001;
  }

  location / {
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_pass http://asking-ng-frontend:80;
  }
}
```

### HAProxy

```haproxy
frontend fe_https
  bind :443 ssl crt /etc/haproxy/certs/asking-ng.pem
  http-response set-header X-Content-Type-Options nosniff
  http-response set-header Referrer-Policy strict-origin-when-cross-origin
  http-response set-header X-Frame-Options SAMEORIGIN
  http-response set-header Permissions-Policy "accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()"
  compression algo gzip
  compression type text/plain text/css application/javascript application/json image/svg+xml

  acl host_asking hdr(host) -i asking-ng.example.com
  acl path_api path_beg /api/
  http-request deny deny_status 413 if host_asking path_api { req.body_size gt 1048576 }
  http-request replace-path ^/api/(.*)$ /\1 if host_asking path_api

  use_backend be_asking_api if host_asking path_api
  use_backend be_asking_frontend if host_asking

backend be_asking_api
  server api asking-ng-api:3001 check

backend be_asking_frontend
  server fe asking-ng-frontend:80 check
```

## Client Build Options Matrix

| Variable | Scope | Effect |
|---|---|---|
| `VITE_PUBLIC_ORIGIN` | client Docker build | Sets absolute `og:image` origin for link previews |
| `VITE_SITE_FOOTER` | client Docker build | Controls footer mode/text |
| `VITE_ATTRIBUTION_URL` | client Docker build | Sets footer link target (`https:` or `http://localhost` only) |
| `VITE_UMAMI_SCRIPT_URL` | client Docker build | Enables optional Umami script loader (`script.js` URL) |
| `VITE_UMAMI_WEBSITE_ID` | client Docker build | Umami website UUID (used as `data-website-id`) |
| `VITE_UMAMI_DOMAINS` | client Docker build | Optional comma-separated Umami `data-domains` hostnames |
| `VITE_PLAUSIBLE_SCRIPT_URL` | client Docker build | Enables optional Plausible script (`js/script.js`) |
| `VITE_PLAUSIBLE_DOMAIN` | client Docker build | Sets Plausible `data-domain` |
| `VITE_MATOMO_BASE_URL` | client Docker build | Enables Matomo loader (`matomo.js` + `matomo.php`) |
| `VITE_MATOMO_SITE_ID` | client Docker build | Sets Matomo site ID |

## Auth Proxy Provider Presets

For self-hosted SSO at the reverse proxy layer, `POST /auth/proxy-login` supports provider header presets via `AUTH_PROXY_PROVIDER`:

- `authentik`: reads `x-authentik-homelab-user` / `x-authentik-email` and `x-authentik-groups`
- `authelia`: reads `remote-user` / `remote-email` and `remote-groups`
- `oauth2-proxy`: reads `x-forwarded-user` / `x-forwarded-email` and `x-forwarded-groups`
- `traefik-forward-auth`: reads `x-forwarded-preferred-homelab-user` / `x-forwarded-user` and `x-forwarded-groups`
- `keycloak`: alias of `traefik-forward-auth` mapping (common Keycloak via forward-auth gateway)
- `generic` (default): reads `AUTH_PROXY_*_HEADER` overrides

Role mapping uses groups first (`superadmin`, `admin`, `operators`), otherwise `AUTH_PROXY_ROLE_HEADER` / `AUTH_PROXY_DEFAULT_ROLE`.

## API Rate Limit and Pressure Tuning

The API now uses two global safeguards:

- `@fastify/rate-limit` for request throttling (`429` when caller exceeds budget)
- `@fastify/under-pressure` for overload shedding (`503` when node process is unhealthy)

Tune these env vars in `stack.env`:

| Variable | Default | What it controls | Increase when | Decrease when |
|---|---|---|---|---|
| `HTTP_RATE_LIMIT_MAX` | `300` | Max requests per window across API routes | Legit traffic bursts are getting `429` | You want tighter abuse resistance |
| `HTTP_RATE_LIMIT_WINDOW_MS` | `60000` | Duration of the rate-limit window | You want smoother longer burst budgets | You want faster reset windows |
| `PRESSURE_MAX_EVENT_LOOP_DELAY_MS` | `1000` | Event loop lag threshold before pressure `503` | CPU spikes trigger false pressure too often | Node becomes unresponsive before shedding |
| `PRESSURE_MAX_HEAP_USED_BYTES` | `0` (disabled) | Optional heap threshold for pressure `503` | You need memory guardrails against leaks | You see unnecessary pressure events |
| `PRESSURE_MAX_RSS_BYTES` | `0` (disabled) | Optional RSS threshold for pressure `503` | Container memory churn needs hard cap | Pressure fires during normal peak usage |

Suggested starting profiles:

| Host profile | Suggested values |
|---|---|
| Small VPS / mini PC (2 vCPU, 2-4 GB RAM) | `HTTP_RATE_LIMIT_MAX=180`, `HTTP_RATE_LIMIT_WINDOW_MS=60000`, `PRESSURE_MAX_EVENT_LOOP_DELAY_MS=700`, `PRESSURE_MAX_HEAP_USED_BYTES=550000000`, `PRESSURE_MAX_RSS_BYTES=1100000000` |
| Mid homelab node (4+ vCPU, 8+ GB RAM) | `HTTP_RATE_LIMIT_MAX=400`, `HTTP_RATE_LIMIT_WINDOW_MS=60000`, `PRESSURE_MAX_EVENT_LOOP_DELAY_MS=1000`, `PRESSURE_MAX_HEAP_USED_BYTES=0`, `PRESSURE_MAX_RSS_BYTES=0` |

Rollout/tuning loop:

1. Apply values in `stack.env` and restart API.
2. Watch API logs for `429` or pressure-related `503` spikes.
3. Run one week with normal traffic before tightening limits aggressively.
4. Tighten in small steps (10-20%) and re-check admin/poll flows after each change.

## Incident Mode Runbook

`INCIDENT_MODE=true` is a fast degradation switch for unstable upstream conditions.

| Behavior | Effect when enabled |
|---|---|
| LLM gateway | `/llm/*` returns `503 LLM_DISABLED` |
| Outbound webhooks | Poll webhooks and integration sinks (`notify`, `audit`, `error`) are skipped |
| Error payload detail | `5xx` responses are redacted to `Service temporarily degraded.` |
| Error logging detail | Server error logs omit raw exception payloads |
| Status history fallback | `GET /status/history` serves static degraded output if DB history query fails |

Recommended toggle flow:

1. Set `INCIDENT_MODE=true` in stack env and restart API.
2. Confirm `GET /llm/status` and `/llm/*` behavior (`503 LLM_DISABLED` for gateway routes).
3. Watch logs for `poll.webhook.skipped_incident_mode` and `status.history.fallback_incident_mode`.
4. Disable incident mode once upstream dependencies stabilize and post-incident checks pass.

## Embed Read-Only URL Grants

For browser overlays and stream tooling that must not hold `api_key`, owner workflows can mint short-lived signed read URLs. Step-by-step OBS and URL usage: [STREAMING-OBS-BROWSER-SOURCE.md](STREAMING-OBS-BROWSER-SOURCE.md).

- Endpoint: `POST /poll/:id/embed-read-url`
- Auth: poll `api_key` **or** owner JWT
- Optional query: `ttl_seconds` (bounded server-side)
- Response includes `poll_url`, `results_url`, `meta_url`, `oembed_url`, `ws_url` with `embed_exp` + `embed_sig`

Notes:

- Signed grants are accepted on read surfaces and live WebSocket subscriptions.
- Vote submission still follows poll vote-gate rules (`embed_token` when enabled).
- For `selection_mode=multi`, each selected option is stored as its own vote row (same anti-abuse gates); public `total_votes` counts rows (checkboxes), not unique ballots—factor that into funnel/velocity interpretation until a dedicated ballot metric exists.
- Rotate embed token (`generate_embed_read_token`) to revoke old token-based access quickly.

## Media Policy Hooks (v1)

Media metadata on polls now supports policy-driven moderation hooks:

- `media_blur_by_default` flag in poll config for safer on-stream rendering defaults.
- Public report endpoint: `POST /poll/:id/media/report` (requires normal poll read access).
- Admin/mod takedown and restore endpoints:
  - `POST /admin/polls/:id/media/takedown`
  - `POST /admin/polls/:id/media/restore`
- Every report/takedown/restore action writes to audit logs for traceability.

Operational guidance:

1. Treat `moderation_status=takedown` as non-display in clients/overlays.
2. Keep blur enabled by default for new media attachments unless explicit policy allows otherwise.
3. Review audit log stream for `poll_media_*` actions during moderation windows.

## Campaign Tracking (UTM)

Poll read requests can carry campaign tags for creator analytics:

- `utm_source`
- `utm_medium`
- `utm_campaign`

Behavior:

1. `GET /poll/:id` increments global `impression_count` as before.
2. When UTM params are present, the API also updates per-poll attribution buckets.
3. Creator `My Polls` includes top campaign buckets so share presets can be compared quickly.
4. `My Polls` distribution presets now provide copy-ready channel URLs plus CTA text snippets for overlay/chat/mobile/results surfaces.
5. Anonymous view events are bucketed by UTC hour (`viewEventsByHour`) and pruned to a rolling 14-day window; `My Polls` surfaces `views_last_24h`, `votes_last_24h`, a 24h conversion percentage, and a per-option funnel summary.

## Per-Poll Theme Presets

- Poll create/update payloads accept `theme_preset` (`default`, `sunset`, `ocean`, `neon`).
- The poll page applies the selected preset with scoped CSS variables (`data-poll-theme`), so the rest of the app theme remains unchanged.
- Owners can set this in `My Polls` to brand individual polls for different shows/campaigns.

## Web Vitals Observability (Loki/Grafana)

Client Core Web Vitals are ingested at `POST /telemetry/web-vitals` and emitted in API logs with:

- `event="telemetry.web_vitals.accepted"`
- metric labels: `metric_name`, `metric_rating`, `navigation_type`
- value fields: `metric_value`, `metric_delta`
- page fields: `page_path`, `page_href`

Starter LogQL queries for Grafana Explore:

```logql
{service="asking-ng-api"} |= "telemetry.web_vitals.accepted" | json | metric_name="LCP"
```

```logql
{service="asking-ng-api"} |= "telemetry.web_vitals.accepted"
| json
| metric_name=~"LCP|INP|CLS"
| line_format "{{.metric_name}} {{.metric_rating}} {{.metric_value}} {{.page_path}}"
```

Count poor events by page path (time series via `count_over_time`):

```logql
sum by (page_path) (
  count_over_time(
    {service="asking-ng-api"} |= "telemetry.web_vitals.accepted"
    | json
    | metric_rating="poor" [15m]
  )
)
```

## API Log Event Catalog

API logs now include structured `event` fields for machine-friendly filtering and alerting.

Event naming conventions:

- Use dot-separated, lowercase namespaces: `<domain>.<subdomain>.<outcome>`.
- Use `*_fallback` suffix for degraded read paths that intentionally switch to legacy/canonical logic.
- Keep event names stable; add new names instead of mutating existing ones used by dashboards/alerts.
- Include `requestId` on request-scoped logs and `pollId` when the event is poll-scoped.
- Prefer one primary `event` per log line; use extra fields for dimensions (`metric_name`, `statusCode`, `provider`, etc.).

Core event families:

- `http.error`: normalized error handler log for API responses
- `db.readiness.failed`: readiness probe DB auth/connectivity failure
- `api.bootstrap.*` / `api.shutdown.*`: process lifecycle and startup guard failures
- `llm.models.upstream_error`, `llm.chat.upstream_error`: LLM upstream failures
- `poll.read_model.*_fallback`, `admin.read_model.*_fallback`: read-model degradation fallback paths
- `read_model.reconcile.summary`: periodic reconcile summary with mismatch count + max diffs
- `read_model.reconcile.alert`: reconcile mismatch thresholds exceeded
- `poll.webhook.*`: webhook validation/delivery outcomes
- `poll.live.ws.*` and `poll.ws.origin_entry_invalid`: websocket guard/upgrade/runtime issues
- `async_job.*`: async runner execution failures
- `db.migrate.*`: migration runner lifecycle and Umzug bridge logs

Starter LogQL queries:

```logql
{service="asking-ng-api"} | json | event="http.error"
```

```logql
{service="asking-ng-api"} | json | event=~"api.bootstrap.*|api.shutdown.*"
```

```logql
sum by (event) (
  count_over_time({service="asking-ng-api"} | json | event=~"llm.*|poll.webhook.*|poll.live.ws.*" [15m])
)
```

```logql
{service="asking-ng-api"} | json | event=~".*_fallback" | line_format "{{.event}} poll={{.pollId}} req={{.requestId}}"
```

```logql
{service="asking-ng-api"} | json | event="read_model.reconcile.alert"
```

```logql
{service="asking-ng-api"} | json | event="read_model.reconcile.summary"
| line_format "mismatch={{.mismatchCount}} max24h={{.maxDiffVotesLast24h}} alert={{.alert}}"
```

### Reconcile trend panels (Grafana/Loki)

Use `read_model.reconcile.summary` as the primary series for dashboard trend lines.

Mismatch count trend:

```logql
max_over_time(
  {service="asking-ng-api"} | json | event="read_model.reconcile.summary" | unwrap mismatchCount [15m]
)
```

Max absolute `votes_last_24h` diff trend:

```logql
max_over_time(
  {service="asking-ng-api"} | json | event="read_model.reconcile.summary" | unwrap maxDiffVotesLast24h [15m]
)
```

Alert-state hit count trend (per window):

```logql
count_over_time(
  {service="asking-ng-api"} | json | event="read_model.reconcile.summary" | alert=true [15m]
)
```

### Reconcile threshold profiles by environment

Starter profiles for `READ_MODEL_RECONCILE_ALERT_*`:

| Environment | `READ_MODEL_RECONCILE_ALERT_MISMATCH_COUNT` | `READ_MODEL_RECONCILE_ALERT_DIFF_THRESHOLD` | Intent |
|---|---:|---:|---|
| Dev | `0` | `0` | Disable hard alerts while validating read-model shape/parity |
| Staging | `3` | `10` | Early-warning without noisy deploy-blocking |
| Production | `1` | `5` | Detect drift quickly once baseline is stable |

Tuning loop:

1. Start with the table defaults.
2. Review one week of `read_model.reconcile.summary` trend panels.
3. Raise thresholds if alerts are noisy but harmless, lower if real drift is missed.
4. Keep `fail_on_alert=1` smoke checks enabled in CI/staging after each threshold change.

### Reconcile overlay rollout checklist

Use this before/after deploys when changing reconcile profile overlays:

1. Select the target overlay (`docker-compose.reconcile-dev.yml`, `docker-compose.reconcile-staging.yml`, or `docker-compose.reconcile-prod.yml`).
   - or use automation shortcut: `pnpm run reconcile:profile:<dev|staging|prod>`
2. Start/update with overlay:
   - `docker compose -f docker-compose.yml -f docker-compose.reconcile-<env>.yml up -d --build`
3. Verify effective env inside API:
   - `docker compose exec asking-api env | grep READ_MODEL_RECONCILE_ALERT_`
4. Run reconcile smoke in fail mode:
   - `set -a; source stack.env.dev; set +a`
   - `cd api && pnpm run read-model:reconcile-smoke`
5. Confirm reconcile summary logs are present:
   - query `event="read_model.reconcile.summary"` in Loki/Grafana.
6. If alert/noise level is unexpected, adjust overlay thresholds and re-run steps 2-5.

### Reconcile rollout sign-off criteria

Mark an environment profile as "stable defaults" only when all criteria pass for 7 consecutive days:

| Criterion | Signal | Pass target |
|---|---|---|
| Reconcile smoke reliability | `pnpm run read-model:reconcile-smoke` in deploy window | 100% pass |
| Reconcile alert noise | `read_model.reconcile.alert` events | <= 1 benign alert per 24h |
| Reconcile drift trend | `read_model.reconcile.summary` max diff panels | No sustained upward drift trend |
| Fallback stability | `poll.read_model.*_fallback` + `admin.read_model.*_fallback` | Below `20 / 15m` under normal traffic |
| Threshold churn | `READ_MODEL_RECONCILE_ALERT_*` values | No changes during observation window |

If any criterion fails, keep profile status as "tuning", adjust overlay thresholds, and restart the observation window.

### Alert candidates (starter thresholds)

Use these as initial non-paging thresholds, then tune per baseline traffic:

- Read-model fallback burst:
  - trigger when fallback events exceed `20 / 15m` per event family.
- Reconcile alert presence:
  - trigger when `read_model.reconcile.alert` appears at least once in a `15m` window.
- HTTP server errors:
  - trigger when `http.error` with `statusCode >= 500` exceeds `10 / 5m`.
- LLM upstream instability:
  - trigger when `llm.models.upstream_error` or `llm.chat.upstream_error` exceeds `5 / 10m`.

Suggested LogQL alert expressions:

```logql
sum by (event) (
  count_over_time(
    {service="asking-ng-api"} | json | event=~"poll.read_model.*_fallback|admin.read_model.*_fallback" [15m]
  )
) > 20
```

```logql
count_over_time({service="asking-ng-api"} | json | event="read_model.reconcile.alert" [15m]) > 0
```

```logql
count_over_time({service="asking-ng-api"} | json | event="http.error" | statusCode >= 500 [5m]) > 10
```

```logql
count_over_time({service="asking-ng-api"} | json | event=~"llm.models.upstream_error|llm.chat.upstream_error" [10m]) > 5
```

## Admin and Role Lifecycle

| Phase | Mechanism | Restriction |
|---|---|---|
| Initial hardening | `ADMIN_TOKEN` + `JWT_SECRET` in `stack.env` | Production boot fails if missing or `changeme` |
| Identity check | `GET /admin/me` | Validates admin token and returns role identity (`mod`/`admin`/`superadmin`) |
| Mod scope | Mod JWT or admin token | Can manage polls (`/admin/polls*`) and read dashboard/status surfaces |
| Normal role management | JWT role routes | `admin` cannot create/assign `superadmin`; only `superadmin` can |
| Bootstrap superadmin | Admin-token API flow | Can create/promote first superadmin only |
| Ongoing superadmin changes | Superadmin JWT | Required after first superadmin exists |

<details>
<summary>Admin UI login behavior</summary>

The **App login** path in Admin -> Users uses `/auth/login` and stores the returned JWT in session storage for that browser tab, enabling role/user actions without manual curl requests.

</details>
