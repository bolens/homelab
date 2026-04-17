#!/usr/bin/env node
import { createHmac, timingSafeEqual } from 'node:crypto';

function fail(msg) {
  console.error(msg);
  process.exit(1);
}

function parseSignature(raw) {
  if (!raw || typeof raw !== 'string') return null;
  const part = raw
    .split(',')
    .map((s) => s.trim())
    .find((s) => s.startsWith('v1='));
  if (!part) return null;
  return part.slice(3);
}

async function readStdinUtf8() {
  const chunks = [];
  for await (const chunk of process.stdin) chunks.push(chunk);
  return Buffer.concat(chunks).toString('utf8');
}

const secret = process.env.ASKING_WEBHOOK_SECRET?.trim() || '';
const tsRaw = process.env.ASKING_WEBHOOK_TS?.trim() || '';
const sigHeader = process.env.ASKING_WEBHOOK_SIG?.trim() || '';
const eventId = process.env.ASKING_WEBHOOK_EVENT_ID?.trim() || '';
const maxSkewSec = Number.parseInt(process.env.ASKING_WEBHOOK_MAX_SKEW_SEC || '300', 10);

if (!secret) fail('Missing ASKING_WEBHOOK_SECRET');
if (!tsRaw || !/^\d+$/.test(tsRaw)) fail('Invalid ASKING_WEBHOOK_TS');
if (!sigHeader) fail('Missing ASKING_WEBHOOK_SIG');

const body = await readStdinUtf8();
if (!body || body.trim() === '') fail('Request body is empty');

const nowSec = Math.floor(Date.now() / 1000);
const ts = Number.parseInt(tsRaw, 10);
if (!Number.isFinite(ts)) fail('Invalid ASKING_WEBHOOK_TS');
if (Math.abs(nowSec - ts) > maxSkewSec) {
  fail(`Timestamp outside skew window (max ${maxSkewSec}s)`);
}

const expected = createHmac('sha256', secret).update(`${tsRaw}.${body}`).digest('hex');
const got = parseSignature(sigHeader);
if (!got) fail('Signature header missing v1=...');

const expectedBuf = Buffer.from(expected, 'hex');
const gotBuf = Buffer.from(got, 'hex');
if (expectedBuf.length !== gotBuf.length || !timingSafeEqual(expectedBuf, gotBuf)) {
  fail('Signature mismatch');
}

const parsed = JSON.parse(body);
const payloadEventId =
  parsed && typeof parsed === 'object' && typeof parsed.event_id === 'string'
    ? parsed.event_id.trim()
    : '';
if (!payloadEventId) fail('Body missing event_id');
if (eventId && eventId !== payloadEventId) fail('Header/body event id mismatch');

// In production, replace this with a persistent idempotency store (Redis/DB).
console.log(
  JSON.stringify({
    ok: true,
    event_id: payloadEventId,
    replay_check: 'store event_id in Redis/DB and reject duplicates',
  }),
);
