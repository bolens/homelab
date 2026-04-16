#!/usr/bin/env node

import { mkdir, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';

const baseUrl = (process.env.API_BASE_URL ?? 'http://127.0.0.1:3001').replace(/\/+$/, '');
const outDir = resolve(process.cwd(), process.env.PERF_BASELINE_OUT_DIR ?? './artifacts/perf');
const timestamp = new Date().toISOString().replaceAll(':', '-');

const pollId = process.env.PERF_BASELINE_POLL_ID ?? '';
const voteBodyRaw = process.env.PERF_BASELINE_VOTE_BODY ?? '';
const iterations = Math.max(
  1,
  Number.parseInt(process.env.PERF_BASELINE_ITERATIONS ?? '20', 10) || 20,
);
const warmup = Math.max(0, Number.parseInt(process.env.PERF_BASELINE_WARMUP ?? '3', 10) || 3);

if (!pollId) {
  process.stderr.write('Missing PERF_BASELINE_POLL_ID for perf baseline script.\n');
  process.exit(1);
}

function parseVoteBody() {
  if (!voteBodyRaw) return null;
  try {
    return JSON.parse(voteBodyRaw);
  } catch {
    process.stderr.write('PERF_BASELINE_VOTE_BODY is not valid JSON.\n');
    process.exit(1);
  }
}

function percentile(sorted, p) {
  if (sorted.length === 0) return null;
  const index = Math.min(sorted.length - 1, Math.max(0, Math.ceil((p / 100) * sorted.length) - 1));
  return sorted[index];
}

async function timedFetch(url, init) {
  const started = Date.now();
  const response = await fetch(url, init);
  await response.text();
  return { duration: Date.now() - started, status: response.status, ok: response.ok };
}

async function runSample(name, reqFactory) {
  const timings = [];
  const statuses = new Map();

  for (let i = 0; i < warmup; i += 1) {
    await timedFetch(...reqFactory());
  }
  for (let i = 0; i < iterations; i += 1) {
    const result = await timedFetch(...reqFactory());
    timings.push(result.duration);
    statuses.set(result.status, (statuses.get(result.status) ?? 0) + 1);
  }

  const sorted = [...timings].sort((a, b) => a - b);
  return {
    name,
    iterations,
    warmup,
    min_ms: sorted[0] ?? null,
    p50_ms: percentile(sorted, 50),
    p95_ms: percentile(sorted, 95),
    max_ms: sorted[sorted.length - 1] ?? null,
    status_counts: Object.fromEntries([...statuses.entries()].sort((a, b) => a[0] - b[0])),
  };
}

async function run() {
  await mkdir(outDir, { recursive: true });
  const voteBody = parseVoteBody();

  const samples = [];
  samples.push(
    await runSample('GET /poll/:id', () => [`${baseUrl}/poll/${pollId}`, { method: 'GET' }]),
  );

  if (voteBody) {
    samples.push(
      await runSample('PUT /poll/:id/vote', () => [
        `${baseUrl}/poll/${pollId}/vote`,
        {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(voteBody),
        },
      ]),
    );
  }

  const output = {
    generated_at: new Date().toISOString(),
    base_url: baseUrl,
    poll_id: pollId,
    samples,
  };

  const file = resolve(outDir, `perf-baseline-${timestamp}.json`);
  await writeFile(file, `${JSON.stringify(output, null, 2)}\n`, 'utf8');
  process.stdout.write(`Wrote perf baseline: ${file}\n`);
}

void run();
