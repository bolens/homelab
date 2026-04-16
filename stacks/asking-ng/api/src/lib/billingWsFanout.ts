import Poll from '../model/Poll';
import { findBillingPlanAndRoleByUserId } from '../controller/self/self.repository';
import { maxWsFanoutMessagesPerSecondForBillingPlan } from './billingLimits';
import { appEnv } from './env';
import { logger } from './logger';

const CACHE_TTL_MS = 60_000;
const planCache = new Map<number, { plan: string; role: string | null; exp: number }>();

/** Last known poll owner for WS fanout metering (set on upgrade; may be filled async for vote-only paths). */
const roomCreatorByPollId = new Map<string, number | null>();
const pendingCreatorFetch = new Set<string>();

class PerPollSecondFanoutLimiter {
  private readonly hits = new Map<string, number[]>();
  private readonly windowMs = 1000;

  take(pollId: string, maxPerSecond: number): boolean {
    const cap = Math.max(1, Math.floor(maxPerSecond));
    const now = Date.now();
    const cutoff = now - this.windowMs;
    let arr = this.hits.get(pollId) ?? [];
    arr = arr.filter((t) => t > cutoff);
    if (arr.length >= cap) {
      this.hits.set(pollId, arr);
      return false;
    }
    arr.push(now);
    this.hits.set(pollId, arr);
    return true;
  }

  pruneStale(): void {
    const cutoff = Date.now() - this.windowMs;
    for (const [k, arr] of this.hits) {
      const next = arr.filter((t) => t > cutoff);
      if (next.length === 0) this.hits.delete(k);
      else this.hits.set(k, next);
    }
  }
}

const limiter = new PerPollSecondFanoutLimiter();

function cachedPlanFields(uid: number): { plan: string; role: string | null } | null {
  const row = planCache.get(uid);
  if (row && row.exp > Date.now()) return { plan: row.plan, role: row.role };
  return null;
}

async function refreshPlanCache(uid: number): Promise<void> {
  try {
    const { billingPlan, role } = await findBillingPlanAndRoleByUserId(uid);
    planCache.set(uid, { plan: billingPlan, role, exp: Date.now() + CACHE_TTL_MS });
  } catch (err: unknown) {
    logger.warn({ event: 'billing.ws_fanout.plan_cache_failed', err, uid }, 'ws fanout plan cache refresh failed');
  }
}

/**
 * Hard ceiling + optional billing tier cap (messages/sec of **server→client** `notifyPollLive` payloads per poll).
 * When `BILLING_ENFORCE_LIMITS` and creator is unknown briefly, returns env cap until `creatorUserId` is cached.
 */
export function effectiveWsFanoutMessagesPerSecondForWorkspace(creatorUserId: number | null): number {
  const envCap = appEnv.wsFanoutMaxPerPollPerSec;
  if (!appEnv.billingEnforceLimits) return envCap;
  const uid =
    typeof creatorUserId === 'number' && Number.isFinite(creatorUserId) && creatorUserId > 0 ? creatorUserId : null;
  if (uid == null) {
    return Math.min(envCap, maxWsFanoutMessagesPerSecondForBillingPlan('free'));
  }
  const c = cachedPlanFields(uid);
  if (c) {
    if (c.role === 'superadmin') return envCap;
    const tier = maxWsFanoutMessagesPerSecondForBillingPlan(c.plan);
    if (tier >= Number.MAX_SAFE_INTEGER / 2) return envCap;
    return Math.min(envCap, tier);
  }
  void refreshPlanCache(uid);
  return envCap;
}

export function setPollLiveRoomCreatorForFanout(pollId: string, creatorUserId: number | null | undefined): void {
  roomCreatorByPollId.set(pollId, creatorUserId ?? null);
}

export function clearPollLiveRoomCreatorForFanout(pollId: string): void {
  roomCreatorByPollId.delete(pollId);
}

/** Best-effort: load `creatorUserId` for fanout when votes fire before any WS client connected. */
export function ensurePollCreatorForFanout(pollId: string): void {
  if (!appEnv.billingEnforceLimits) return;
  if (roomCreatorByPollId.has(pollId)) return;
  if (pendingCreatorFetch.has(pollId)) return;
  pendingCreatorFetch.add(pollId);
  void (async () => {
    try {
      const poll = await Poll.findByPk(pollId, { attributes: ['creatorUserId'] });
      const cid = poll?.get('creatorUserId') as number | null | undefined;
      setPollLiveRoomCreatorForFanout(
        pollId,
        typeof cid === 'number' && Number.isFinite(cid) && cid > 0 ? cid : null,
      );
    } catch (err: unknown) {
      logger.warn({ event: 'billing.ws_fanout.creator_lookup_failed', err, pollId }, 'ws fanout creator lookup failed');
    } finally {
      pendingCreatorFetch.delete(pollId);
    }
  })();
}

/**
 * Returns false when this outbound burst would exceed the per-poll per-second fanout cap (shed broadcast).
 * Logs `USAGE_LIMIT_WS_FANOUT` for operators; clients do not receive a payload for dropped `update`s.
 */
export function takePollLiveFanoutOrShed(pollId: string): boolean {
  ensurePollCreatorForFanout(pollId);
  const uidForCap = roomCreatorByPollId.has(pollId) ? (roomCreatorByPollId.get(pollId) ?? null) : null;
  const cap = effectiveWsFanoutMessagesPerSecondForWorkspace(uidForCap);
  const ok = limiter.take(pollId, cap);
  if (!ok) {
    logger.warn(
      { event: 'poll.live.ws_fanout_shed', pollId, code: 'USAGE_LIMIT_WS_FANOUT', cap },
      'poll live outbound fanout cap exceeded for this poll; update broadcast dropped',
    );
  }
  return ok;
}

export function prunePollLiveFanoutLimiter(): void {
  limiter.pruneStale();
}
