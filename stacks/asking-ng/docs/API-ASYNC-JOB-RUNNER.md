# Asking-NG Async Job Runner Path

## Goal

Provide a safe async execution path for heavy/remote side effects (webhooks first, exports next) without blocking API response latency.

## Implementation in this pass

- Added `api/src/lib/asyncJobs.ts`:
  - in-process async queue
  - configurable concurrency via `ASYNC_JOB_RUNNER_CONCURRENCY`
  - toggle via `ASYNC_JOB_RUNNER_ENABLED`
  - graceful shutdown hook (`stopAsyncJobs`) used during API shutdown
- Wired webhook dispatch to async jobs:
  - `queuePollWebhook()` now enqueues one async task per validated webhook target.
  - When async runner is disabled, jobs run inline fire-and-forget (backward-compatible behavior).

## Runtime env vars

- `ASYNC_JOB_RUNNER_ENABLED` (`true|false`, default `false`)
- `ASYNC_JOB_RUNNER_CONCURRENCY` (default `2`, max `16`)

## Follow-up (exports)

- Current export endpoint remains synchronous for API contract parity.
- Next increment can introduce a dedicated async export job endpoint (job id + polling/download contract) reusing `asyncJobs.ts`.

