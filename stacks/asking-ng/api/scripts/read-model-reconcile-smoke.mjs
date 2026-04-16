#!/usr/bin/env node

import { mkdir, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';

const baseUrl = (process.env.RECONCILE_SMOKE_BASE_URL ?? 'http://127.0.0.1:3001').replace(/\/+$/, '');
const adminToken = (process.env.RECONCILE_SMOKE_ADMIN_TOKEN ?? '').trim();
const limit = Math.max(1, Math.min(500, Number.parseInt(process.env.RECONCILE_SMOKE_LIMIT ?? '100', 10) || 100));
const diffThreshold = Math.max(
  0,
  Number.parseInt(process.env.RECONCILE_SMOKE_DIFF_THRESHOLD ?? '0', 10) || 0,
);
const failOnAlert = (process.env.RECONCILE_SMOKE_FAIL_ON_ALERT ?? 'true').trim().toLowerCase() !== 'false';
const outDir = resolve(process.cwd(), process.env.RECONCILE_SMOKE_OUT_DIR ?? './artifacts/reconcile');
const timestamp = new Date().toISOString().replaceAll(':', '-');

if (!adminToken) {
  process.stderr.write('Missing RECONCILE_SMOKE_ADMIN_TOKEN.\n');
  process.exit(2);
}

async function run() {
  await mkdir(outDir, { recursive: true });
  const params = new URLSearchParams();
  params.set('limit', String(limit));
  params.set('diff_threshold', String(diffThreshold));
  if (failOnAlert) params.set('fail_on_alert', '1');
  const url = `${baseUrl}/admin/read-model/reconcile?${params.toString()}`;

  const started = Date.now();
  const response = await fetch(url, {
    headers: {
      'x-admin-token': adminToken,
    },
  });
  const elapsedMs = Date.now() - started;
  const text = await response.text();
  let json = null;
  try {
    json = text ? JSON.parse(text) : null;
  } catch {
    // keep raw payload when upstream returns non-JSON
  }

  const output = {
    generated_at: new Date().toISOString(),
    base_url: baseUrl,
    request: {
      limit,
      diff_threshold: diffThreshold,
      fail_on_alert: failOnAlert,
    },
    response: {
      status_code: response.status,
      ok: response.ok,
      elapsed_ms: elapsedMs,
      body: json ?? text,
    },
    pass: response.ok,
  };

  const file = resolve(outDir, `read-model-reconcile-smoke-${timestamp}.json`);
  await writeFile(file, `${JSON.stringify(output, null, 2)}\n`, 'utf8');
  process.stdout.write(`Wrote reconcile smoke report: ${file}\n`);

  if (!response.ok) {
    const reason =
      response.status === 503 && failOnAlert
        ? 'reconcile returned alert state (503 with fail_on_alert=1)'
        : `unexpected status ${response.status}`;
    process.stderr.write(`RECONCILE SMOKE FAIL: ${reason}\n`);
    process.exit(2);
  }
}

void run();
