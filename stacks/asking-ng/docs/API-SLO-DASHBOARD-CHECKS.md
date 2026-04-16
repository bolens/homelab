# API SLO and Dashboard Checks

## Purpose

Operational runbook for API latency/reliability smoke checks and monitoring validation loops.

## Use This When

- You need a quick pass/fail signal for core API health after deploys.
- You are tuning read-model reconcile thresholds and want repeatable checks.
- You are validating Prometheus/Alertmanager/Loki wiring before tightening alerts.

## Related Docs

- [../README.md](../README.md)
- [OPERATIONS.md](OPERATIONS.md)
- [API-READ-MODEL-STRATEGY.md](API-READ-MODEL-STRATEGY.md)
- [API-MIGRATION-TRACKER.md](API-MIGRATION-TRACKER.md)

## Goal

Keep a lightweight, repeatable health/performance guardrail for key API endpoints after cutover.

## Current SLO smoke checks

Script: `api/scripts/slo-smoke.mjs`  
NPM: `pnpm run slo:smoke`

Default checks:

- `GET /ready`
- `GET /poll/:id`

Default budgets:

- `p95 <= 250ms`
- `success_rate >= 99%`

## Runbook

From `stacks/asking-ng/api`:

```bash
SLO_SMOKE_BASE_URL=http://127.0.0.1:18081 \
SLO_SMOKE_POLL_ID=<existing-poll-id> \
pnpm run slo:smoke
```

Artifact output:

- `api/artifacts/slo/slo-smoke-<timestamp>.json`

Fail behavior:

- Script exits non-zero and lists failed checks when budgets are missed.

## Tunables

- `SLO_SMOKE_ITERATIONS` (default `20`)
- `SLO_SMOKE_WARMUP` (default `3`)
- `SLO_SMOKE_P95_BUDGET_MS` (default `250`)
- `SLO_SMOKE_SUCCESS_RATE_PCT` (default `99`)
- `SLO_SMOKE_OUT_DIR` (default `./artifacts/slo`)

## Dashboard tie-in

For homelab dashboards, track these time series per deploy window:

- `ready_p95_ms`
- `poll_read_p95_ms`
- `ready_success_rate_pct`
- `poll_read_success_rate_pct`

The generated JSON artifact is intentionally simple so it can be shipped into log/metric pipelines if needed.

## Read-model reconcile smoke

Script: `api/scripts/read-model-reconcile-smoke.mjs`  
NPM: `pnpm run read-model:reconcile-smoke`

From `stacks/asking-ng/api`:

```bash
RECONCILE_SMOKE_BASE_URL=http://127.0.0.1:18081 \
RECONCILE_SMOKE_ADMIN_TOKEN=<admin-token> \
pnpm run read-model:reconcile-smoke
```

Default behavior:

- Calls `GET /admin/read-model/reconcile` with `fail_on_alert=1`.
- Fails non-zero on any non-2xx status (including `503` alert state).
- Writes `api/artifacts/reconcile/read-model-reconcile-smoke-<timestamp>.json`.

Tunables:

- `RECONCILE_SMOKE_LIMIT` (default `100`)
- `RECONCILE_SMOKE_DIFF_THRESHOLD` (default `0`)
- `RECONCILE_SMOKE_FAIL_ON_ALERT` (default `true`)
- `RECONCILE_SMOKE_OUT_DIR` (default `./artifacts/reconcile`)

## Monitoring smoke (Prometheus/Alertmanager/Loki)

Script: `scripts/monitoring-smoke-check.sh`  
Make target: `make monitoring-smoke-check`

Default behavior:

- Verifies required Prometheus jobs and loaded alert rules.
- Verifies Alertmanager readiness.
- Validates key Loki LogQL alert queries for fallback/reconcile/http/llm event families.

Loki tunables (optional):

- `LOKI_CONTAINER` (default `loki`)
- `LOKI_QUERY_WINDOW` (default `15m`)
- `LOKI_ENFORCE_THRESHOLDS` (default `0`)
- `LOKI_FALLBACK_THRESHOLD` (default `20`)
- `LOKI_RECONCILE_THRESHOLD` (default `0`)
- `LOKI_HTTP_5XX_THRESHOLD` (default `10`)
- `LOKI_LLM_UPSTREAM_THRESHOLD` (default `5`)

## Reconcile profile overlays

To apply environment-specific reconcile thresholds without editing `stack.env`, use compose overlays:

- `docker-compose.reconcile-dev.yml`
- `docker-compose.reconcile-staging.yml`
- `docker-compose.reconcile-prod.yml`

Example (staging profile):

```bash
docker compose \
  -f docker-compose.yml \
  -f docker-compose.reconcile-staging.yml \
  up -d --build
```

Automation shortcut:

```bash
pnpm run reconcile:profile:staging
```

This applies the overlay, prints effective reconcile env values from `asking-api`, and runs reconcile smoke (unless `--no-verify` is used with the script directly).

Rollout verification quick check:

```bash
docker compose exec asking-api env | grep READ_MODEL_RECONCILE_ALERT_
set -a; source stack.env.dev; set +a
cd api && pnpm run read-model:reconcile-smoke
```

## Reconcile threshold sign-off criteria

Treat reconcile defaults as stable for an environment only when all checks pass for at least 7 consecutive days:

1. **Smoke reliability:** `read-model:reconcile-smoke` succeeds on every deploy window (no unexpected non-2xx).
2. **Alert noise budget:** `read_model.reconcile.alert` does not fire more than 1 time per 24h for known-benign drift.
3. **Drift trend stability:** `read_model.reconcile.summary` max diff trends stay within expected range for that environment profile.
4. **No fallback surge:** read-model fallback events do not exceed current threshold budget (`20 / 15m`) during normal traffic.
5. **No manual threshold edits:** `READ_MODEL_RECONCILE_ALERT_*` values remain unchanged for the full observation window.

If any check fails, keep status as tuning-in-progress, adjust profile thresholds, and restart the 7-day window.

Trend report helper (JSON artifact from API logs):

- `pnpm run reconcile:trend:24h`
- `pnpm run reconcile:trend:7d`

Artifacts are written to `artifacts/reconcile-trends/` and summarize:

- sample count
- alert sample count + rate
- max mismatch count
- max diff fields from `read_model.reconcile.summary`

