#!/usr/bin/env node

import { mkdir, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';

const baseUrl = (process.env.SLO_SMOKE_BASE_URL ?? 'http://127.0.0.1:3001').replace(/\/+$/, '');
const configuredPollId = (process.env.SLO_SMOKE_POLL_ID ?? '').trim();
const iterations = Math.max(1, Number.parseInt(process.env.SLO_SMOKE_ITERATIONS ?? '20', 10) || 20);
const warmup = Math.max(0, Number.parseInt(process.env.SLO_SMOKE_WARMUP ?? '3', 10) || 3);
const p95BudgetMs = Math.max(
  1,
  Number.parseInt(process.env.SLO_SMOKE_P95_BUDGET_MS ?? '250', 10) || 250,
);
const successRateBudgetPct = Math.min(
  100,
  Math.max(1, Number.parseInt(process.env.SLO_SMOKE_SUCCESS_RATE_PCT ?? '99', 10) || 99),
);
const outDir = resolve(process.cwd(), process.env.SLO_SMOKE_OUT_DIR ?? './artifacts/slo');
const timestamp = new Date().toISOString().replaceAll(':', '-');
const bootstrapPoll =
  (process.env.SLO_SMOKE_BOOTSTRAP_POLL ?? 'true').trim().toLowerCase() !== 'false';
const cleanupBootstrapPoll =
  (process.env.SLO_SMOKE_CLEANUP_BOOTSTRAP ?? 'true').trim().toLowerCase() !== 'false';

function percentile(sorted, p) {
  if (sorted.length === 0) return null;
  const index = Math.min(sorted.length - 1, Math.max(0, Math.ceil((p / 100) * sorted.length) - 1));
  return sorted[index];
}

async function timedFetch(url) {
  const started = Date.now();
  const response = await fetch(url);
  await response.text();
  return { durationMs: Date.now() - started, status: response.status, ok: response.ok };
}

async function resolvePollTarget() {
  if (configuredPollId) {
    return { pollId: configuredPollId, cleanup: null, source: 'configured' };
  }
  if (!bootstrapPoll) {
    throw new Error(
      'Missing SLO_SMOKE_POLL_ID and SLO_SMOKE_BOOTSTRAP_POLL=false, cannot determine poll target.',
    );
  }

  const now = Date.now();
  const response = await fetch(`${baseUrl}/poll`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      title: `SLO smoke ${timestamp}`,
      options: ['A', 'B'],
      expiration: now + 60 * 60 * 1000,
      limit_ip: false,
    }),
  });
  const bodyText = await response.text();
  if (!response.ok) {
    throw new Error(`Bootstrap poll creation failed (${response.status}): ${bodyText}`);
  }

  let parsed;
  try {
    parsed = JSON.parse(bodyText);
  } catch {
    throw new Error('Bootstrap poll creation returned non-JSON payload');
  }
  const pollId = parsed?.data?.id;
  const apiKey = parsed?.data?.api_key;
  if (typeof pollId !== 'string' || pollId.trim() === '') {
    throw new Error('Bootstrap poll creation response missing data.id');
  }

  const cleanup =
    cleanupBootstrapPoll && typeof apiKey === 'string' && apiKey.trim() !== ''
      ? async () => {
          await fetch(`${baseUrl}/poll/${encodeURIComponent(pollId)}`, {
            method: 'DELETE',
            headers: { api_key: apiKey },
          });
        }
      : null;

  return { pollId, cleanup, source: 'bootstrap' };
}

async function sample(name, path) {
  const timings = [];
  let okCount = 0;
  const statuses = new Map();
  const url = `${baseUrl}${path}`;

  for (let i = 0; i < warmup; i += 1) {
    await timedFetch(url);
  }
  for (let i = 0; i < iterations; i += 1) {
    const result = await timedFetch(url);
    timings.push(result.durationMs);
    if (result.ok) okCount += 1;
    statuses.set(result.status, (statuses.get(result.status) ?? 0) + 1);
  }

  const sorted = [...timings].sort((a, b) => a - b);
  const successRatePct = Number(((okCount / iterations) * 100).toFixed(2));
  return {
    name,
    path,
    iterations,
    warmup,
    min_ms: sorted[0] ?? null,
    p50_ms: percentile(sorted, 50),
    p95_ms: percentile(sorted, 95),
    max_ms: sorted[sorted.length - 1] ?? null,
    success_rate_pct: successRatePct,
    status_counts: Object.fromEntries([...statuses.entries()].sort((a, b) => a[0] - b[0])),
  };
}

async function run() {
  await mkdir(outDir, { recursive: true });
  const pollTarget = await resolvePollTarget();
  const checks = [
    await sample('ready', '/ready'),
    await sample('poll-read', `/poll/${pollTarget.pollId}`),
  ];

  const budgets = {
    p95_budget_ms: p95BudgetMs,
    success_rate_pct: successRateBudgetPct,
  };
  const failures = checks.flatMap((check) => {
    const issues = [];
    if ((check.p95_ms ?? Infinity) > p95BudgetMs) {
      issues.push(`${check.name}: p95 ${check.p95_ms}ms exceeds budget ${p95BudgetMs}ms`);
    }
    if (check.success_rate_pct < successRateBudgetPct) {
      issues.push(
        `${check.name}: success rate ${check.success_rate_pct}% below budget ${successRateBudgetPct}%`,
      );
    }
    return issues;
  });

  const output = {
    generated_at: new Date().toISOString(),
    base_url: baseUrl,
    poll_id: pollTarget.pollId,
    poll_id_source: pollTarget.source,
    budgets,
    checks,
    pass: failures.length === 0,
    failures,
  };
  const file = resolve(outDir, `slo-smoke-${timestamp}.json`);
  await writeFile(file, `${JSON.stringify(output, null, 2)}\n`, 'utf8');
  process.stdout.write(`Wrote SLO smoke report: ${file}\n`);
  if (pollTarget.cleanup) {
    await pollTarget.cleanup();
  }
  if (failures.length > 0) {
    for (const f of failures) process.stderr.write(`SLO FAIL: ${f}\n`);
    process.exit(2);
  }
}

void run();
