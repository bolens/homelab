#!/usr/bin/env node

import { mkdir, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';

const baseUrl = (process.env.API_BASE_URL ?? 'http://127.0.0.1:3001').replace(/\/+$/, '');
const outDir = resolve(process.cwd(), process.env.CONTRACT_SNAPSHOT_OUT_DIR ?? './artifacts/contracts');
const timestamp = new Date().toISOString().replaceAll(':', '-');

const pollId = process.env.CONTRACT_SNAPSHOT_POLL_ID ?? ':id';
const authToken = process.env.CONTRACT_SNAPSHOT_AUTH_BEARER?.trim() || '';

function authHeaders() {
  return authToken ? { Authorization: `Bearer ${authToken}` } : {};
}

const checks = [
  {
    name: 'healthcheck',
    method: 'GET',
    path: '/healthcheck',
    headers: {},
  },
  {
    name: 'ready',
    method: 'GET',
    path: '/ready',
    headers: {},
  },
  {
    name: 'llm-status',
    method: 'GET',
    path: '/llm/status',
    headers: authHeaders(),
  },
  {
    name: 'poll-meta',
    method: 'GET',
    path: `/poll/${pollId}/meta`,
    headers: {},
  },
];

async function safeJson(response) {
  const text = await response.text();
  try {
    return { json: JSON.parse(text), text };
  } catch {
    return { json: null, text };
  }
}

async function run() {
  await mkdir(outDir, { recursive: true });
  const results = [];

  for (const check of checks) {
    const url = `${baseUrl}${check.path}`;
    const startedAt = Date.now();
    try {
      const response = await fetch(url, {
        method: check.method,
        headers: check.headers,
      });
      const body = await safeJson(response);
      results.push({
        name: check.name,
        request: {
          method: check.method,
          path: check.path,
          headers: Object.keys(check.headers).sort(),
        },
        response: {
          status: response.status,
          ok: response.ok,
          duration_ms: Date.now() - startedAt,
          json: body.json,
          text: body.json == null ? body.text : null,
        },
      });
    } catch (error) {
      results.push({
        name: check.name,
        request: { method: check.method, path: check.path },
        response: {
          status: null,
          ok: false,
          duration_ms: Date.now() - startedAt,
          error: error instanceof Error ? error.message : String(error),
        },
      });
    }
  }

  const output = {
    generated_at: new Date().toISOString(),
    base_url: baseUrl,
    poll_id: pollId,
    checks: results,
  };

  const file = resolve(outDir, `contract-snapshot-${timestamp}.json`);
  await writeFile(file, `${JSON.stringify(output, null, 2)}\n`, 'utf8');
  process.stdout.write(`Wrote contract snapshot: ${file}\n`);
}

void run();
