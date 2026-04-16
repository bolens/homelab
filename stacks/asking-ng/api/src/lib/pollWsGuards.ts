import type { IncomingMessage } from 'node:http';
import { logger } from './logger';

/** Parse `true` / `1` / `yes` (case-insensitive). */
export function envTruthy(v: string | undefined): boolean {
  const s = (v ?? '').trim().toLowerCase();
  return s === 'true' || s === '1' || s === 'yes';
}

/**
 * Normalize a user-configured origin entry to `scheme://host[:port]` (no path).
 * Accepts `https://app.example` or `app.example` (defaults to https).
 */
export function normalizeOriginEntry(entry: string): string | null {
  const t = entry.trim();
  if (!t) return null;
  try {
    const u = new URL(t.includes('://') ? t : `https://${t}`);
    if (!u.hostname) return null;
    return u.origin;
  } catch {
    logger.warn({ event: 'poll.ws.origin_entry_invalid', entry: t }, 'poll ws: invalid origin entry skipped');
    return null;
  }
}

/** Build allowlist: `WS_ALLOWED_ORIGINS` if non-empty after trim, else `CORS_ORIGIN`. */
export function buildWsAllowedOriginSet(): ReadonlySet<string> {
  const wsRaw = (process.env.WS_ALLOWED_ORIGINS ?? '').trim();
  const corsRaw = (process.env.CORS_ORIGIN ?? '').trim();
  const raw = wsRaw.length > 0 ? wsRaw : corsRaw;
  const out = new Set<string>();
  for (const part of raw.split(',')) {
    const o = normalizeOriginEntry(part);
    if (o) out.add(o);
  }
  return out;
}

/**
 * When `allowed` is empty, all origins are accepted (dev / private reverse-proxy).
 * When non-empty, `Origin` must match unless `allowMissingOrigin` (e.g. health probes).
 */
export function isWsOriginAllowed(
  originHeader: string | undefined,
  allowed: ReadonlySet<string>,
  allowMissingOrigin: boolean,
): boolean {
  if (allowed.size === 0) return true;
  const o = originHeader?.trim();
  if (!o) return allowMissingOrigin;
  try {
    return allowed.has(new URL(o).origin);
  } catch {
    return false;
  }
}

/** Client IP for upgrade rate limiting (first `X-Forwarded-For` hop when present). */
export function clientIpForUpgrade(req: IncomingMessage): string {
  const xff = req.headers['x-forwarded-for'];
  if (typeof xff === 'string') {
    const first = xff.split(',')[0]?.trim();
    if (first) return first;
  }
  return req.socket.remoteAddress ?? '0.0.0.0';
}

/** Sliding window: at most `max` events per `windowMs` per key. */
export class SlidingWindowRateLimit {
  private readonly hits = new Map<string, number[]>();

  constructor(
    private readonly max: number,
    private readonly windowMs: number,
  ) {}

  take(key: string): boolean {
    const now = Date.now();
    const cutoff = now - this.windowMs;
    let arr = this.hits.get(key) ?? [];
    arr = arr.filter((t) => t > cutoff);
    if (arr.length >= this.max) {
      this.hits.set(key, arr);
      return false;
    }
    arr.push(now);
    this.hits.set(key, arr);
    return true;
  }

  /** Best-effort cap on map size (called occasionally from accept path). */
  pruneStale(): void {
    const cutoff = Date.now() - this.windowMs;
    for (const [k, arr] of this.hits) {
      const next = arr.filter((t) => t > cutoff);
      if (next.length === 0) this.hits.delete(k);
      else this.hits.set(k, next);
    }
  }
}
