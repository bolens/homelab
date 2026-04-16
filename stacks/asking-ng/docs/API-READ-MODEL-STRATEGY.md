# Asking-NG Read Model Strategy

## Goal

Reduce load from analytics-heavy poll endpoints by serving pre-aggregated data instead of repeatedly scanning raw `votes`.

## Scope (initial rollout)

- `GET /admin/status`
- `GET /poll/:id/meta` moderation counters
- `GET /poll/:id/replay` and `GET /poll/:id/heatmap` (read-path acceleration only)

## Read-model tables

1. `poll_vote_rollups`
   - `poll_id` (pk)
   - `total_votes`
   - `votes_last_1m`
   - `votes_last_24h`
   - `quarantined_votes_pending`
   - `updated_at`

2. `poll_vote_time_bins_hourly`
   - `poll_id`
   - `hour_bucket_utc` (timestamp/hour floor)
   - `vote_count`
   - primary key: (`poll_id`, `hour_bucket_utc`)
   - rollout status: implemented for `/admin/status` global hour/day peak + histograms behind `READ_MODEL_ENABLED`

3. `poll_vote_geo_bins`
   - `poll_id`
   - `latitude_bucket` (coarse decimal, 1dp)
   - `longitude_bucket` (coarse decimal, 1dp)
   - `vote_count`
   - primary key: (`poll_id`, `latitude_bucket`, `longitude_bucket`)
   - rollout status: implemented for `/poll/:id/heatmap` behind `READ_MODEL_ENABLED`

4. `poll_vote_replay_events`
   - `poll_id`
   - `sequence_no`
   - `option_label`
   - `offset_ms`
   - primary key: (`poll_id`, `sequence_no`)
   - rollout status: implemented for `/poll/:id/replay` behind `READ_MODEL_ENABLED`

3. `poll_vote_actor_rollups`
   - `poll_id`
   - `window_start_utc` (minute floor)
   - `unique_ip_hashes`
   - `unique_accounts`
   - `top_ip_votes`
   - primary key: (`poll_id`, `window_start_utc`)

## Update flow

- Keep writes authoritative in existing `votes` table.
- On vote write success:
  - enqueue a lightweight rollup update task (or apply inline upsert for first pass).
- For batch moderation changes:
  - enqueue poll-level recompute task for affected poll ids.

## Query routing

- Keep endpoint contracts unchanged.
- Add repository-level feature flag:
  - `READ_MODEL_ENABLED=true` -> prefer read-model tables
  - fallback to current SQL paths if rollup row missing.
- For poll-scoped analytics endpoints (`/poll/:id/meta`, `/poll/:id/replay`, `/poll/:id/heatmap`):
  - run a throttled poll-level read-model refresh before reading rollup rows to reduce staleness without global rebuild pressure.

## Structured log events (fallback visibility)

When read-model reads fail and the API falls back to canonical SQL paths, structured `event` fields are emitted:

- Poll endpoints:
  - `poll.read_model.rollup_fallback`
  - `poll.read_model.replay_fallback`
  - `poll.read_model.heatmap_fallback`
- Admin status:
  - `admin.read_model.global_votes_fallback`
  - `admin.read_model.time_bins_fallback`

These events are designed for alerting and deploy-window verification.

Example LogQL queries:

```logql
{service="asking-ng-api"} | json | event=~"poll.read_model.*_fallback|admin.read_model.*_fallback"
```

```logql
sum by (event) (
  count_over_time({service="asking-ng-api"} | json | event=~".*_fallback" [15m])
)
```

```logql
{service="asking-ng-api"} | json | event=~"poll.read_model.*_fallback" | line_format "{{.event}} poll={{.pollId}} req={{.requestId}}"
```

## Correctness guardrails

- Daily reconciliation job:
  - compare rollups vs canonical `votes` aggregates
  - emit audit log on mismatch above threshold.
- Keep rollup updates idempotent (`INSERT ... ON CONFLICT DO UPDATE`).
- `GET /admin/read-model/reconcile` now returns `data.alert` based on:
  - `READ_MODEL_RECONCILE_ALERT_MISMATCH_COUNT`
  - `READ_MODEL_RECONCILE_ALERT_DIFF_THRESHOLD`
- Reconcile responses also include `data.max_diffs` for dashboard-friendly trend panels.
- API emits `read_model.reconcile.summary` with mismatch count + max diff dimensions for time-series alert tuning.
- Monitoring mode: call reconcile with `fail_on_alert=1` to return HTTP `503` when thresholds are breached.
- Per-environment threshold recommendations are defined in `docs/OPERATIONS.md` and mirrored in `stack.env.example`.

## Rollout plan

1. Add schema + repository readers behind feature flag.
2. Populate backfill once from existing votes.
3. Enable in staging/dev and compare against legacy query output. (In progress: `/admin/status`, `/poll/:id/meta`, `/poll/:id/heatmap`, `/poll/:id/replay`)
4. Enable in production with reconciliation alarms.

