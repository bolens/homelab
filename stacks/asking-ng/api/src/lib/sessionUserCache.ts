/**
 * Short-lived cache for {@link ../middleware/requireSession} to cut DB load on busy sessions.
 * TTL defaults to 2s (see `SESSION_CACHE_TTL_MS`). Only active users are cached; call
 * {@link invalidateSessionUserCache} after suspend, activate, role change, password reset, or delete.
 */
import { appEnv } from './env';

export type SessionUserSnapshot = {
  id: number;
  homelab-user: string;
  role: string;
  active: boolean;
  /** Mirrored workspace plan; used for per-tier HTTP caps when `BILLING_ENFORCE_LIMITS` is on. */
  billingPlan: string;
};

const ttlMs = Math.max(500, appEnv.sessionCacheTtlMs);

const cache = new Map<number, { snapshot: SessionUserSnapshot; expiresAt: number }>();

export function getSessionUserFromCache(userId: number): SessionUserSnapshot | null {
  const row = cache.get(userId);
  if (!row) return null;
  if (row.expiresAt <= Date.now()) {
    cache.delete(userId);
    return null;
  }
  return row.snapshot;
}

export function setSessionUserCache(snapshot: SessionUserSnapshot): void {
  if (!snapshot.active) return;
  cache.set(snapshot.id, { snapshot, expiresAt: Date.now() + ttlMs });
}

export function invalidateSessionUserCache(userId: number): void {
  cache.delete(userId);
}
