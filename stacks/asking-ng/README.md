# asking-ng 🗳️

Lightweight poll application (frontend + API + PostgreSQL) for homelab deployment.

| Quick facts | Value |
|---|---|
| Repo layout assumption | This tree is the repository root (`api/`, `client/`, `docker-compose.yml`) when asking-ng is standalone |
| Homepage | <https://asking-ng> |
| Upstream inspiration | <https://github.com/jdleo/asking> |

## Purpose

Primary operator quickstart and navigation hub for running `asking-ng` in a homelab.

## Use This When

- You need the fastest path from clone to healthy stack.
- You want common commands, troubleshooting, and env essentials in one place.
- You need links to deeper docs (API, CI/repo workflow, operations, migration tracker).

## Related Docs

- [docs/API-REFERENCE.md](docs/API-REFERENCE.md)
- [docs/CI-REPO-WORKFLOW.md](docs/CI-REPO-WORKFLOW.md)
- [docs/OPERATIONS.md](docs/OPERATIONS.md)
- [docs/API-SLO-DASHBOARD-CHECKS.md](docs/API-SLO-DASHBOARD-CHECKS.md)
- [docs/API-MIGRATION-TRACKER.md](docs/API-MIGRATION-TRACKER.md)
- [docs/MONETIZATION-AND-PACKAGING.md](docs/MONETIZATION-AND-PACKAGING.md) (hosted tiers, limits, billing roadmap)
- [docs/OSS-AND-COMMERCIAL-POSITIONING.md](docs/OSS-AND-COMMERCIAL-POSITIONING.md) (OSS vs paid narrative + contribution boundary)
- [docs/POLAR-BILLING.md](docs/POLAR-BILLING.md) (default hosted billing + webhooks)
- [docs/CREATOR-STREAMER-ROADMAP.md](docs/CREATOR-STREAMER-ROADMAP.md) (creator / streamer backlog)
- [docs/STREAMING-OBS-BROWSER-SOURCE.md](docs/STREAMING-OBS-BROWSER-SOURCE.md) (OBS / browser overlays)

## Table of Contents

- [Reader Paths](#reader-paths)
- [Packaging and monetization (roadmap)](#packaging-and-monetization-roadmap)
- [Hostname](#hostname)
- [5-Minute Setup](#5-minute-setup)
- [Troubleshooting Quick Table](#troubleshooting-quick-table)
- [Command Cookbook](#command-cookbook)
  - [Ops Validation Cadence](#ops-validation-cadence)
  - [Web Vitals Observability (Loki/Grafana)](#web-vitals-observability-lokigrafana)
- [Monitoring & SLO Runbooks](#monitoring--slo-runbooks)
- [Script Environment Reference](#script-environment-reference)
- [Environment Variable Index](#environment-variable-index)
- [Configuration Model (Like Modern Hosted Apps)](#configuration-model-like-modern-hosted-apps)
- [First-Run UX Checklist](#first-run-ux-checklist)
- [CI (GitHub Actions)](#ci-github-actions)
- [JavaScript Workspace (pnpm)](#javascript-workspace-pnpm)
- [Database Migration Policy](#database-migration-policy)
- [Local Development (Vite+)](#local-development-vite)
- [Public API Quick Reference](#public-api-quick-reference)
- [Operational Notes](#operational-notes)

## Reader Paths

| If you are... | Read this first | Then go here |
|---|---|---|
| Deploying in homelab | [5-minute setup](#5-minute-setup) | [Troubleshooting quick table](#troubleshooting-quick-table), [Operational notes](#operational-notes) |
| Developing features | [Local development (Vite+)](#local-development-vite) | [Public API quick reference](#public-api-quick-reference), [JavaScript workspace (pnpm)](#javascript-workspace-pnpm) |
| Debugging incidents | [Troubleshooting quick table](#troubleshooting-quick-table) | [Command cookbook](#command-cookbook), [Public API quick reference](#public-api-quick-reference) |
| Migrating architecture | [Database migration policy](#database-migration-policy) | [docs/API-MIGRATION-TRACKER.md](docs/API-MIGRATION-TRACKER.md) |
| Splitting from monorepo | [CI (GitHub Actions)](#ci-github-actions) | [docs/CI-REPO-WORKFLOW.md](docs/CI-REPO-WORKFLOW.md) |
| Product / commercial roadmap | [Packaging and monetization (roadmap)](#packaging-and-monetization-roadmap) | [docs/MONETIZATION-AND-PACKAGING.md](docs/MONETIZATION-AND-PACKAGING.md), [docs/OSS-AND-COMMERCIAL-POSITIONING.md](docs/OSS-AND-COMMERCIAL-POSITIONING.md), [docs/CREATOR-STREAMER-ROADMAP.md](docs/CREATOR-STREAMER-ROADMAP.md) |
| Stream overlays (OBS) | [docs/STREAMING-OBS-BROWSER-SOURCE.md](docs/STREAMING-OBS-BROWSER-SOURCE.md) | [OPERATIONS.md — Embed grants](docs/OPERATIONS.md#embed-read-only-url-grants), [API-REFERENCE.md](docs/API-REFERENCE.md) |

## Packaging and monetization (roadmap)

asking-ng is **open-source friendly** at the core (polls, votes, basic moderation). A separate spec describes **hosted plans**, **self-host Pro**, **hard usage limits**, **add-ons**, **enterprise contact-sales**, and optional **regulated / platform-sensitive modules** (real-money wagering, event markets, loyalty-currency markets). That spec is the handoff for billing, entitlements, and ops when you run a commercial offering.

- **Canonical doc:** [docs/MONETIZATION-AND-PACKAGING.md](docs/MONETIZATION-AND-PACKAGING.md)
- **OSS vs commercial positioning:** [docs/OSS-AND-COMMERCIAL-POSITIONING.md](docs/OSS-AND-COMMERCIAL-POSITIONING.md)
- **Feature backlog vs tiers:** [docs/CREATOR-STREAMER-ROADMAP.md](docs/CREATOR-STREAMER-ROADMAP.md)
- **Runtime / degraded behavior:** [docs/OPERATIONS.md](docs/OPERATIONS.md) (Plans, entitlements, and degraded behavior)
- **API limit codes (planned):** [docs/API-REFERENCE.md](docs/API-REFERENCE.md)

## Hostname

- Placeholder public URL: `https://asking-ng.example.com`
- Internal Caddy targets: `http://asking-ng-frontend:80` (SPA) and `http://asking-ng-api:3001` (`/api/*`)

## 5-Minute Setup

### 1) Bootstrap local files

```bash
./prepare-stack.sh
```

What this does:

| Item | Result |
|---|---|
| `stack.env` | Created from example if missing |
| `caddy_snippet.conf.example` | Synced from `caddy_snippet.conf.template` |
| `caddy_snippet.conf` | Created from example if missing (or rendered when `ASKING_NG_PUBLIC_HOSTNAME` is set) |
| Docker network `monitor` | Created if missing |

### 2) Set required secrets in `stack.env`

Set these first, then bring the stack up:

| Variable | Required | How to choose value | Why it matters |
|---|---|---|---|
| `POSTGRES_PASSWORD` | Yes | Long random password (at least 24 chars) | Used by Postgres and API DB auth |
| `JWT_SECRET` | Yes | Strong random secret (recommended: `openssl rand -hex 64`) | Signs user JWTs; weak/missing value fails startup |
| `ADMIN_TOKEN` | Yes | Long random token distinct from other secrets | Protects `/admin/*` routes |

Example generation commands:

```bash
openssl rand -hex 32   # good for POSTGRES_PASSWORD or ADMIN_TOKEN
openssl rand -hex 64   # recommended for JWT_SECRET
```

Example `stack.env` snippet:

```env
POSTGRES_PASSWORD=replace_with_random_hex_32
JWT_SECRET=replace_with_random_hex_64
ADMIN_TOKEN=replace_with_random_hex_32
```

Implementation notes:

| Topic | Behavior |
|---|---|
| DB env source | Postgres + API read `POSTGRES_*` from `env_file` (not project `.env`) |
| DB URI fallback | API builds `DATABASE_URI` from `POSTGRES_USER`, `POSTGRES_PASSWORD`, and `POSTGRES_DB` unless `DATABASE_URI` is set directly |
| Startup guard | API runs with `NODE_ENV=production`; weak or missing `JWT_SECRET` exits at startup |

### 3) (Optional) Set your public hostname

Use this only when exposing asking-ng externally.

| File | Change | Example |
|---|---|---|
| `caddy_snippet.conf` | Replace placeholder hostname with your real public hostname | `asking-ng.example.com` -> `polls.yourdomain.com` |

Quick check:

```bash
rg "example.com|asking-ng.example.com" caddy_snippet.conf
```

Optional: pre-render local snippet with your hostname from template:

```bash
ASKING_NG_PUBLIC_HOSTNAME=polls.example.com ./scripts/sync-caddy-snippets.sh
```

### 4) Start services

Run command:

```bash
docker compose up -d --build
```

Why this is enough:

| Scope | Effect |
|---|---|
| Compose parse-time vars | Not required for default deploy path |
| Container runtime env | Passed via `env_file` as usual |

Need loopback API access on the host for local smoke/debug:

| Step | Action |
|---|---|
| 1 | (Optional) set `ASKING_NG_API_HOST_PORT` in `stack.env` to a free port |
| 2 | Start with debug override: `docker compose -f docker-compose.yml -f docker-compose.debug.yml up -d --build` |

### 5) Verify app is healthy

Run checks:

```bash
docker compose ps
docker compose exec asking-api wget -qO- http://127.0.0.1:3001/ready
docker compose exec asking-api wget -qO- http://127.0.0.1:3001/info
```

Expected outcomes:

| Check | Success signal | Meaning |
|---|---|---|
| `docker compose ps` | Services show `Up`/healthy | Containers are running |
| `GET /ready` | `2xx` response | API can reach/authenticate to DB |
| `GET /info` | `2xx` response | API endpoint is reachable |

If all checks pass, open the app at your configured hostname (or local Caddy route).

## Troubleshooting Quick Table

| Symptom | Likely cause | Fix |
|---|---|---|
| `Bind for ... :8080 failed` | Debug override is enabled and host port 8080 is in use | Set `ASKING_NG_API_HOST_PORT` in `stack.env` and rerun with `-f docker-compose.debug.yml` |
| API container exits on boot | Missing/weak `JWT_SECRET` or `ADMIN_TOKEN` in production | Set strong values in `stack.env`, then recreate container |
| `GET /ready` returns `503` | DB credentials mismatch or DB unavailable | Recheck `POSTGRES_*`, verify `asking-db` is healthy, restart stack |
| `/admin` requests fail auth | Wrong `ADMIN_TOKEN` in request or env mismatch | Confirm `ADMIN_TOKEN` in `stack.env` and admin client/header usage |
| Public URL not serving app | Placeholder hostname left in `caddy_snippet.conf` | Replace host and reload/restart Caddy |
| LLM routes return `503 LLM_DISABLED` | `INCIDENT_MODE=true` | Disable incident mode (or keep enabled intentionally during incident response) |

## Command Cookbook

| Task | Command |
|---|---|
| Start/update stack | `docker compose up -d --build` |
| Start stack with reconcile profile | `docker compose -f docker-compose.yml -f docker-compose.reconcile-staging.yml up -d --build` |
| Apply reconcile profile + verify | `pnpm run reconcile:profile:staging` |
| Run command with `stack.env.dev` loaded | `bash scripts/with-dev-env.sh <command> [args...]` |
| Show service state | `docker compose ps` |
| Follow logs (all services) | `docker compose logs -f` |
| Follow API logs only | `docker compose logs -f asking-api` |
| Health probes (internal) | `docker compose exec asking-api wget -qO- http://127.0.0.1:3001/ready && docker compose exec asking-api wget -qO- http://127.0.0.1:3001/info` |
| Health probes (host loopback debug, local only) | `docker compose -f docker-compose.yml -f docker-compose.debug.yml up -d asking-api && curl -fsS http://127.0.0.1:8080/ready` |
| Restart API only | `docker compose restart asking-api` |
| Stop stack | `docker compose down` |
| Full dev reset (drops volumes) | `docker compose down -v && docker compose up -d --build` |
| JS verify pipeline | `pnpm run verify` |
| API SLO smoke (from `api/`) | `bash ../scripts/with-dev-env.sh pnpm run slo:smoke` |
| API reconcile smoke (from `api/`) | `bash ../scripts/with-dev-env.sh pnpm run read-model:reconcile-smoke` |
| API perf baseline (from `api/`) | `bash ../scripts/with-dev-env.sh pnpm run perf:baseline` |
| API contract snapshot (from `api/`) | `bash ../scripts/with-dev-env.sh pnpm run contracts:snapshot` |
| API SLO smoke (stack root shortcut) | `pnpm run devenv:slo-smoke` |
| API reconcile smoke (stack root shortcut) | `pnpm run devenv:reconcile-smoke` |
| Reconcile trend report (24h) | `pnpm run reconcile:trend:24h` |
| Reconcile trend report (7d) | `pnpm run reconcile:trend:7d` |
| API perf baseline (stack root shortcut) | `pnpm run devenv:perf-baseline` |
| API contract snapshot (stack root shortcut) | `pnpm run devenv:contracts-snapshot` |

Monitoring smoke details (Prometheus/Alertmanager/Loki + `LOKI_*` tunables): [docs/API-SLO-DASHBOARD-CHECKS.md#monitoring-smoke-prometheusalertmanagerloki](docs/API-SLO-DASHBOARD-CHECKS.md#monitoring-smoke-prometheusalertmanagerloki).

### Ops Validation Cadence

Use this lightweight checklist when you change compose/env/Caddy or before/after upgrades.

| Cadence | Run | Expected |
|---|---|---|
| Every deploy | `docker compose ps` and `docker compose exec asking-api wget -qO- http://127.0.0.1:3001/ready` | Services up and readiness returns `2xx` |
| Weekly | `docker compose logs --since=168h asking-api` | No recurring auth/DB/panic errors |
| After env changes | `docker compose exec asking-api wget -qO- http://127.0.0.1:3001/info` and a login to `/admin` | API metadata reachable and admin auth works |
| After Caddy/domain changes | Open app URL and run one poll vote flow | Frontend routing + edge `/api/*` proxy + vote path all work |

For scripted smoke-check runbooks and thresholds, see [docs/API-SLO-DASHBOARD-CHECKS.md](docs/API-SLO-DASHBOARD-CHECKS.md).

### Web Vitals Observability (Loki/Grafana)

Client Core Web Vitals are ingested at `POST /telemetry/web-vitals` and logged by the API with:

- `event="telemetry.web_vitals.accepted"`
- metric labels: `metric_name`, `metric_rating`, `navigation_type`
- value fields: `metric_value`, `metric_delta`
- page fields: `page_path`, `page_href`

Use these starter LogQL queries in Grafana Explore:

```logql
{service="asking-ng-api"} |= "telemetry.web_vitals.accepted" | json | metric_name="LCP"
```

```logql
{service="asking-ng-api"} |= "telemetry.web_vitals.accepted"
| json
| metric_name=~"LCP|INP|CLS"
| line_format "{{.metric_name}} {{.metric_rating}} {{.metric_value}} {{.page_path}}"
```

Count poor events by page path (turn into time series with `count_over_time`):

```logql
sum by (page_path) (
  count_over_time(
    {service="asking-ng-api"} |= "telemetry.web_vitals.accepted"
    | json
    | metric_rating="poor" [15m]
  )
)
```

## Script Environment Reference

These env vars are only used when running API utility scripts from `stacks/asking-ng/api`.
They are grouped in `stack.env.dev.example` (copy to local `stack.env.dev` as needed).

| Script | Command | Key env vars | Defaults |
|---|---|---|---|
| Contract snapshot | `pnpm run contracts:snapshot` | `CONTRACT_SNAPSHOT_POLL_ID`, `CONTRACT_SNAPSHOT_AUTH_BEARER`, `CONTRACT_SNAPSHOT_OUT_DIR` | poll `:id`, no auth header, `./artifacts/contracts` |
| Perf baseline | `pnpm run perf:baseline` | `PERF_BASELINE_POLL_ID` (required), `PERF_BASELINE_VOTE_BODY`, `PERF_BASELINE_ITERATIONS`, `PERF_BASELINE_WARMUP`, `PERF_BASELINE_OUT_DIR` | iter `20`, warmup `3`, `./artifacts/perf` |
| SLO smoke | `pnpm run slo:smoke` | `SLO_SMOKE_BASE_URL`, `SLO_SMOKE_POLL_ID`, `SLO_SMOKE_ITERATIONS`, `SLO_SMOKE_WARMUP`, `SLO_SMOKE_P95_BUDGET_MS`, `SLO_SMOKE_SUCCESS_RATE_PCT`, `SLO_SMOKE_BOOTSTRAP_POLL`, `SLO_SMOKE_CLEANUP_BOOTSTRAP`, `SLO_SMOKE_OUT_DIR` | base `http://127.0.0.1:3001`, iter `20`, warmup `3`, p95 `250`, success `99`, bootstrap+cleanup `true`, `./artifacts/slo` |
| Reconcile smoke | `pnpm run read-model:reconcile-smoke` | `RECONCILE_SMOKE_BASE_URL`, `RECONCILE_SMOKE_ADMIN_TOKEN` (required), `RECONCILE_SMOKE_LIMIT`, `RECONCILE_SMOKE_DIFF_THRESHOLD`, `RECONCILE_SMOKE_FAIL_ON_ALERT`, `RECONCILE_SMOKE_OUT_DIR` | base `http://127.0.0.1:3001`, limit `100`, diff `0`, fail-on-alert `true`, `./artifacts/reconcile` |
| Monitoring smoke (repo root) | `bash scripts/monitoring-smoke-check.sh` | `LOKI_CONTAINER`, `LOKI_QUERY_WINDOW`, `LOKI_ENFORCE_THRESHOLDS`, `LOKI_FALLBACK_THRESHOLD`, `LOKI_RECONCILE_THRESHOLD`, `LOKI_HTTP_5XX_THRESHOLD`, `LOKI_LLM_UPSTREAM_THRESHOLD` | container `loki`, window `15m`, enforce `0`, fallback `20`, reconcile `0`, http5xx `10`, llm `5` |

## Environment Variable Index

Key variables most operators touch first. Runtime/deploy list and comments live in `stack.env.example`.
Dev/script knobs live in `stack.env.dev.example`.

| Variable | Required | Scope | Default/example | Purpose |
|---|---|---|---|---|
| `POSTGRES_DB` | Yes | Runtime | `asking` | Postgres database name |
| `POSTGRES_USER` | Yes | Runtime | `asking` | Postgres user |
| `POSTGRES_PASSWORD` | Yes | Runtime | `REPLACE_WITH_GENERATED_PASSWORD` | Postgres/API DB auth |
| `JWT_SECRET` | Yes | Runtime | `REPLACE_WITH_OPENSSL_RAND_HEX_64` | JWT signing secret |
| `ADMIN_TOKEN` | Yes | Runtime | `REPLACE_WITH_LONG_RANDOM_SECRET` | Admin API protection |
| `ASKING_NG_API_HOST_PORT` | Optional | Compose parse-time (debug override only) | `8080` (default) | Loopback host port for API when `docker-compose.debug.yml` is used |
| `ENABLE_API_DOCS` | Optional | Runtime | `false` in production unless set | Enable `/api-docs` in production |
| `EXPOSE_SERVICE_INFO_DETAILS` | Optional | Runtime | `false` in production unless set | Add metadata to `/info` |
| `HTTP_RATE_LIMIT_MAX` | Optional | Runtime | `300` | Global API request cap per rate-limit window |
| `HTTP_RATE_LIMIT_WINDOW_MS` | Optional | Runtime | `60000` | Global API rate-limit window in milliseconds |
| `PRESSURE_MAX_EVENT_LOOP_DELAY_MS` | Optional | Runtime | `1000` | Backpressure trigger threshold for event loop lag |
| `PRESSURE_MAX_HEAP_USED_BYTES` | Optional | Runtime | `0` (disabled) | Optional heap ceiling for pressure shedding |
| `PRESSURE_MAX_RSS_BYTES` | Optional | Runtime | `0` (disabled) | Optional RSS memory ceiling for pressure shedding |
| `VITE_PUBLIC_ORIGIN` | Optional | Build-time (client) | `https://asking-ng.example.com` | Absolute OG/Twitter preview URLs |
| `VITE_SITE_FOOTER` | Optional | Build-time (client) | `default`/`hidden` | Footer rendering mode |
| `VITE_ATTRIBUTION_URL` | Optional | Build-time (client) | `https://github.com/jdleo/asking` | Footer attribution link |
| `VITE_UMAMI_SCRIPT_URL` | Optional | Build-time (client) | `https://umami.example.com/script.js` | Enables Umami script injection (requires website ID) |
| `VITE_UMAMI_WEBSITE_ID` | Optional | Build-time (client) | `00000000-0000-0000-0000-000000000000` | Umami website UUID paired with script URL |
| `VITE_UMAMI_DOMAINS` | Optional | Build-time (client) | `asking-ng.example.com` | Optional comma-separated Umami `data-domains` |
| `VITE_PLAUSIBLE_SCRIPT_URL` | Optional | Build-time (client) | `https://plausible.example.com/js/script.js` | Enables Plausible script injection (requires domain) |
| `VITE_PLAUSIBLE_DOMAIN` | Optional | Build-time (client) | `asking-ng.example.com` | Plausible `data-domain` value |
| `VITE_MATOMO_BASE_URL` | Optional | Build-time (client) | `https://matomo.example.com` | Enables Matomo tracker script (requires site ID) |
| `VITE_MATOMO_SITE_ID` | Optional | Build-time (client) | `1` | Matomo site ID |
| `ENABLE_PROMETHEUS_METRICS` | Optional | Runtime | `false` | Exposes `GET /metrics` for Prometheus scrapes |
| `NOTIFY_WEBHOOK_URL` | Optional | Runtime | `https://notify.example.com/hooks/asking-ng` | Sends optional integration notifications (admin/webhook events) |
| `AUDIT_LOG_SINK_URL` | Optional | Runtime | `https://audit.example.com/ingest` | Mirrors audit events to external sink |
| `SENTRY_COMPAT_WEBHOOK_URL` | Optional | Runtime | `https://errors.example.com/ingest` | Sends server-side 5xx summaries to compatible error sink |
| `INTEGRATION_CIRCUIT_BREAKER_THRESHOLD` | Optional | Runtime | `5` | Consecutive sink failures before opening breaker |
| `INTEGRATION_CIRCUIT_BREAKER_COOLDOWN_MS` | Optional | Runtime | `60000` | Breaker open cooldown per sink |
| `AUTH_PROXY_ENABLED` | Optional | Runtime | `false` | Enables `/auth/proxy-login` for trusted forward-auth headers |
| `AUTH_PROXY_PROVIDER` | Optional | Runtime | `generic`/`authentik`/`authelia`/`oauth2-proxy`/`traefik-forward-auth`/`keycloak` | Chooses header preset for self-hosted auth providers |
| `AUTH_PROXY_TRUSTED_IPS` | Optional | Runtime | `127.0.0.1,172.18.0.0/16` | Restricts `/auth/proxy-login` source IP/CIDR |
| `LLM_PROVIDER` | Optional | Runtime | `ollama` or `lmstudio` | Enable local LLM gateway |
| `LLM_GATEWAY_TOKEN` | Required if LLM enabled in production | Runtime | `REPLACE_WITH_OPENSSL_RAND_HEX_32` | Protect `/llm/*` gateway routes |
| `ENABLE_PLATFORM_WEBHOOKS` | Optional | Runtime | `false` | Enable `/platform/webhooks/*` routes |
| `PLATFORM_WEBHOOK_SHARED_SECRET` | Required when platform webhooks enabled | Runtime | `REPLACE_WITH_OPENSSL_RAND_HEX_32` | Webhook request authentication |
| `ASYNC_JOB_RUNNER_ENABLED` | Optional | Runtime | `false` | Enable in-process async worker path for side effects (webhooks now, export jobs next) |
| `ASYNC_JOB_RUNNER_CONCURRENCY` | Optional | Runtime | `2` | Max concurrent async jobs per API process (used when async runner enabled) |
| `ASYNC_JOB_QUEUE_MAX` | Optional | Runtime | `5000` | Max queued async jobs before non-critical drops |
| `READ_MODEL_ENABLED` | Optional | Runtime | `false` | Enable read-model rollup queries for heavy analytics paths (`/admin/status` first rollout) |
| `READ_MODEL_RECONCILE_ALERT_MISMATCH_COUNT` | Optional | Runtime | `0` | Reconcile alert threshold by mismatch row count (`0` disables count trigger) |
| `READ_MODEL_RECONCILE_ALERT_DIFF_THRESHOLD` | Optional | Runtime | `0` | Reconcile alert threshold by absolute vote diff (`0` disables diff trigger) |
| `stack.env.dev.example` vars | Optional | Dev/script env | n/a | Optional script-only knobs (`SLO_SMOKE_*`, `RECONCILE_SMOKE_*`, `PERF_BASELINE_*`, `CONTRACT_SNAPSHOT_*`, `LOKI_*`) |

Compose overlays for reconcile threshold profiles:

- `docker-compose.reconcile-dev.yml`
- `docker-compose.reconcile-staging.yml`
- `docker-compose.reconcile-prod.yml`

Profile automation helper:

- `scripts/apply-reconcile-profile.sh <dev|staging|prod> [--no-verify]`
- Root shortcuts: `pnpm run reconcile:profile:dev|staging|prod`

## Monitoring & SLO Runbooks

- API latency/reliability smoke + reconcile checks: [docs/API-SLO-DASHBOARD-CHECKS.md](docs/API-SLO-DASHBOARD-CHECKS.md)
- Monitoring smoke (Prometheus/Alertmanager/Loki): [docs/API-SLO-DASHBOARD-CHECKS.md#monitoring-smoke-prometheusalertmanagerloki](docs/API-SLO-DASHBOARD-CHECKS.md#monitoring-smoke-prometheusalertmanagerloki)
- Structured API event catalog + alert-candidate LogQL: [docs/OPERATIONS.md#api-log-event-catalog](docs/OPERATIONS.md#api-log-event-catalog)

## Configuration Model (Like Modern Hosted Apps)

To reduce setup friction, treat config as progressive layers:

1. **Required for first boot**: database + auth secrets (`POSTGRES_*`, `JWT_SECRET`, `ADMIN_TOKEN`)
2. **Recommended for production hardening**: CORS, origin, logging, websocket + LLM allowlists
3. **Feature flags**: Swagger in production, LLM gateway, service info detail exposure

For recommended per-environment reconcile thresholds (dev/staging/production), use the profile table in `docs/OPERATIONS.md`.

`stack.env.example` is organized for deploy/runtime so the first successful deploy does not require reading every script-related option.

## First-Run UX Checklist

After stack is up, follow this flow (mirrors typical SaaS admin onboarding):

1. Open `/admin`
2. Authenticate with `ADMIN_TOKEN`
3. Use **Admin -> Users -> App login** with a superadmin account
4. Create or promote additional users/roles as needed
5. Create a poll, vote once, and confirm results render
6. (Optional) open `/developer` to validate Swagger + LLM integration

## CI (GitHub Actions)

CI workflow details, root-repo requirements, monorepo extraction steps, and Buildx guidance are documented in [docs/CI-REPO-WORKFLOW.md](docs/CI-REPO-WORKFLOW.md).

| Need | Go to |
|---|---|
| Which workflow file does what | [docs/CI-REPO-WORKFLOW.md#workflow-summary](docs/CI-REPO-WORKFLOW.md#workflow-summary) |
| Why Actions may not run in nested paths | [docs/CI-REPO-WORKFLOW.md#root-requirement-for-github-actions](docs/CI-REPO-WORKFLOW.md#root-requirement-for-github-actions) |
| How to split this project from monorepo | [docs/CI-REPO-WORKFLOW.md#split-out-from-a-monorepo-optional](docs/CI-REPO-WORKFLOW.md#split-out-from-a-monorepo-optional) |
| Buildx warning and next steps | [docs/CI-REPO-WORKFLOW.md#docker-buildx-warning](docs/CI-REPO-WORKFLOW.md#docker-buildx-warning) |

## JavaScript Workspace (pnpm)

This repo is a **pnpm workspace** (`api` + `client`) with a single lockfile at the root.

```bash
# From the repo root (where package.json + pnpm-lock.yaml live)
pnpm install
pnpm run check:ci    # Biome on client + api sources
pnpm run verify      # Biome + recursive lint/knip/typecheck/tests/build
```

Fan-out scripts: `pnpm -r run typecheck`, `pnpm -r run test`, `pnpm -r run build`, and `pnpm --filter client|api run <script>`.

## Database Migration Policy

| Lifecycle stage | Policy |
|---|---|
| Pre-launch (no production data) | Squashing/rewriting migration history is allowed |
| Current baseline | Only **`api/src/migrations/00-baseline-prelaunch.ts`**: `sync()` from registered models (see `api/src/lib/migrate.ts` imports) + rollup helper tables + workspace backfill SQL; recorded in **`SequelizeMeta`** as `00-baseline-prelaunch` |
| Post-launch | Add new numbered forward-only migrations; do not rewrite the baseline once production depends on it |
| Schema changes | Update Sequelize models first; new migrations only for backfills, indexes, or constraints `sync()` does not cover |
| Dev reset workflow | `docker compose down -v && docker compose up -d --build` recreates Postgres and reapplies baseline |

## Local Development (Vite+)

Use [Vite+](https://viteplus.dev/) (`vp`) for **client and API**; both list `vite-plus` as a **devDependency**, so `pnpm exec vp …` works after a root `pnpm install`.

```bash
pnpm install

# API (port 3001; scripts use `vp` / `vp exec` — e.g. nodemon + tsx for dev)
pnpm --filter api run dev

# Client (Vite dev server on 3000 per vite.config.ts)
pnpm --filter client exec vp dev
```

Or from `client/`: `./start-all.sh` starts the API in the background, then **`vp dev`** (requires `pnpm install` at the repo root first).

## Public API Quick Reference

Use this as an operator-facing index. Detailed route/auth/error matrices now live in [docs/API-REFERENCE.md](docs/API-REFERENCE.md).

| Need | Go to |
|---|---|
| Full endpoint map and route families | [docs/API-REFERENCE.md](docs/API-REFERENCE.md) |
| Auth and access matrix | [docs/API-REFERENCE.md#auth-and-access-matrix](docs/API-REFERENCE.md#auth-and-access-matrix) |
| Error envelope and DB error mapping | [docs/API-REFERENCE.md#response-and-error-model](docs/API-REFERENCE.md#response-and-error-model) |
| Poll lifecycle, moderation, and anti-abuse rules | [docs/API-REFERENCE.md#poll-lifecycle-and-moderation-flow](docs/API-REFERENCE.md#poll-lifecycle-and-moderation-flow) |
| Swagger/OpenAPI UI | `/api-docs` (when `ENABLE_API_DOCS=true` in production) |
| API migration status | [docs/API-MIGRATION-TRACKER.md](docs/API-MIGRATION-TRACKER.md) |

## Operational Notes

Operational topology, networking model, client build options, and admin role lifecycle are documented in [docs/OPERATIONS.md](docs/OPERATIONS.md).

| Need | Go to |
|---|---|
| Runtime topology and ingress flow | [docs/OPERATIONS.md#traffic-and-networking-model](docs/OPERATIONS.md#traffic-and-networking-model) |
| API rate limiting and backpressure tuning | [docs/OPERATIONS.md#api-rate-limit-and-pressure-tuning](docs/OPERATIONS.md#api-rate-limit-and-pressure-tuning) |
| Structured log event taxonomy and LogQL examples | [docs/OPERATIONS.md#api-log-event-catalog](docs/OPERATIONS.md#api-log-event-catalog) |
| Client build-time env options | [docs/OPERATIONS.md#client-build-options-matrix](docs/OPERATIONS.md#client-build-options-matrix) |
| Admin role and bootstrap lifecycle | [docs/OPERATIONS.md#admin-and-role-lifecycle](docs/OPERATIONS.md#admin-and-role-lifecycle) |
| Adjacent operations docs | [docs/BACKUP-RESTORE-RUNBOOK.md](docs/BACKUP-RESTORE-RUNBOOK.md), [docs/OPS-BACKUP.md](docs/OPS-BACKUP.md) |

