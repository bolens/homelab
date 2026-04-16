import { describe, expect, it } from 'vitest';
import {
  buildWsAllowedOriginSet,
  clientIpForUpgrade,
  envTruthy,
  isWsOriginAllowed,
  normalizeOriginEntry,
  SlidingWindowRateLimit,
} from './pollWsGuards';

describe('normalizeOriginEntry', () => {
  it('normalizes full URL', () => {
    expect(normalizeOriginEntry('https://poll.example/path')).toBe('https://poll.example');
  });

  it('returns null for garbage', () => {
    expect(normalizeOriginEntry('not a url !!!')).toBeNull();
  });
});

describe('isWsOriginAllowed', () => {
  it('allows any when set is empty', () => {
    expect(isWsOriginAllowed(undefined, new Set(), false)).toBe(true);
    expect(isWsOriginAllowed('https://evil.com', new Set(), false)).toBe(true);
  });

  it('requires match when set is non-empty', () => {
    const allowed = new Set(['https://good.example']);
    expect(isWsOriginAllowed('https://good.example', allowed, false)).toBe(true);
    expect(isWsOriginAllowed('https://bad.example', allowed, false)).toBe(false);
  });

  it('optional missing origin', () => {
    const allowed = new Set(['https://good.example']);
    expect(isWsOriginAllowed(undefined, allowed, false)).toBe(false);
    expect(isWsOriginAllowed(undefined, allowed, true)).toBe(true);
  });
});

describe('SlidingWindowRateLimit', () => {
  it('blocks after max in window', () => {
    const lim = new SlidingWindowRateLimit(3, 60_000);
    expect(lim.take('a')).toBe(true);
    expect(lim.take('a')).toBe(true);
    expect(lim.take('a')).toBe(true);
    expect(lim.take('a')).toBe(false);
    expect(lim.take('b')).toBe(true);
  });
});

describe('clientIpForUpgrade', () => {
  it('uses first x-forwarded-for', () => {
    const req = {
      headers: { 'x-forwarded-for': '203.0.113.1, 10.0.0.1' },
      socket: { remoteAddress: '127.0.0.1' },
    } as unknown as import('node:http').IncomingMessage;
    expect(clientIpForUpgrade(req)).toBe('203.0.113.1');
  });

  it('falls back to socket', () => {
    const req = {
      headers: {},
      socket: { remoteAddress: '::1' },
    } as unknown as import('node:http').IncomingMessage;
    expect(clientIpForUpgrade(req)).toBe('::1');
  });
});

describe('buildWsAllowedOriginSet', () => {
  const origWs = process.env.WS_ALLOWED_ORIGINS;
  const origCors = process.env.CORS_ORIGIN;

  it('prefers WS_ALLOWED_ORIGINS over CORS_ORIGIN', () => {
    process.env.WS_ALLOWED_ORIGINS = 'https://ws-only.example';
    process.env.CORS_ORIGIN = 'https://cors.example';
    const s = buildWsAllowedOriginSet();
    expect(s.has('https://ws-only.example')).toBe(true);
    expect(s.has('https://cors.example')).toBe(false);
  });

  it('falls back to CORS_ORIGIN when WS unset', () => {
    delete process.env.WS_ALLOWED_ORIGINS;
    process.env.CORS_ORIGIN = 'https://from-cors.example';
    const s = buildWsAllowedOriginSet();
    expect(s.has('https://from-cors.example')).toBe(true);
  });

  it('falls back to CORS when WS is empty string', () => {
    process.env.WS_ALLOWED_ORIGINS = '';
    process.env.CORS_ORIGIN = 'https://fallback.example';
    const s = buildWsAllowedOriginSet();
    expect(s.has('https://fallback.example')).toBe(true);
  });

  it('returns empty when neither set', () => {
    delete process.env.WS_ALLOWED_ORIGINS;
    delete process.env.CORS_ORIGIN;
    expect(buildWsAllowedOriginSet().size).toBe(0);
  });

  afterEach(() => {
    if (origWs === undefined) delete process.env.WS_ALLOWED_ORIGINS;
    else process.env.WS_ALLOWED_ORIGINS = origWs;
    if (origCors === undefined) delete process.env.CORS_ORIGIN;
    else process.env.CORS_ORIGIN = origCors;
  });
});

describe('envTruthy', () => {
  it('parses common truthy strings', () => {
    expect(envTruthy('true')).toBe(true);
    expect(envTruthy('1')).toBe(true);
    expect(envTruthy('yes')).toBe(true);
    expect(envTruthy('false')).toBe(false);
    expect(envTruthy(undefined)).toBe(false);
  });
});
