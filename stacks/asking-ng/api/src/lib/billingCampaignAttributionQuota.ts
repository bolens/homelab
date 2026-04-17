import AuditLog from '../models/auditlog.sequelize';
import { maxCampaignAttributionIncrementsPerUtcDayForBillingPlan } from './billingLimits';
import { resolvePollWebhookDeliveryScope } from './billingPollWebhookDelivery';
import { appEnv } from './env';
import { logger } from './logger';
import { observeIntegrationEvent } from './metrics';

const buckets = new Map<string, number>();
export const CAMPAIGN_ATTRIBUTION_SHED_AUDIT_ACTION = 'usage.campaign_attribution_shed';

/** Test-only: clears in-memory campaign attribution counters. */
export function resetCampaignAttributionMeterForTests(): void {
  buckets.clear();
}

function utcDayKey(ms: number): string {
  const d = new Date(ms);
  const y = d.getUTCFullYear();
  const m = String(d.getUTCMonth() + 1).padStart(2, '0');
  const day = String(d.getUTCDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

/** `scopeKey` may contain `:` (e.g. `w:12`); day is ISO `YYYY-MM-DD` — join with `::` so pruning is unambiguous. */
function meterKey(scopeKey: string, day: string): string {
  return `${scopeKey}::${day}`;
}

function pruneBuckets(todayKey: string): void {
  for (const k of buckets.keys()) {
    const i = k.lastIndexOf('::');
    if (i <= 0) {
      buckets.delete(k);
      continue;
    }
    const day = k.slice(i + 2);
    if (day !== todayKey) {
      buckets.delete(k);
    }
  }
}

function takeCampaignAttributionDaySlot(scopeKey: string, billingPlan: string): boolean {
  const max = maxCampaignAttributionIncrementsPerUtcDayForBillingPlan(billingPlan);
  if (max >= Number.MAX_SAFE_INTEGER / 2) return true;
  const day = utcDayKey(Date.now());
  pruneBuckets(day);
  const key = meterKey(scopeKey, day);
  const next = (buckets.get(key) ?? 0) + 1;
  if (next > max) return false;
  buckets.set(key, next);
  return true;
}

/**
 * When {@link appEnv.billingEnforceLimits} is on, counts UTM-bearing **attributed** view increments
 * per billing workspace per UTC day. Returns false when over cap (caller skips `impressionAttribution` update).
 */
export async function takeCampaignAttributionIncrementForPoll(args: {
  pollId: string;
  creatorUserId: number | null | undefined;
}): Promise<boolean> {
  if (!appEnv.billingEnforceLimits) return true;
  const cid = args.creatorUserId;
  if (cid == null || !Number.isFinite(cid) || cid <= 0) return true;
  const scope = await resolvePollWebhookDeliveryScope({
    pollId: args.pollId,
    creatorUserId: cid,
  });
  if (!scope) return true;
  if (scope.role === 'superadmin') return true;

  const ok = takeCampaignAttributionDaySlot(scope.scopeKey, scope.billingPlan);
  if (!ok) {
    const max = maxCampaignAttributionIncrementsPerUtcDayForBillingPlan(scope.billingPlan);
    await recordCampaignAttributionShed({
      creatorUserId: args.creatorUserId,
      pollId: args.pollId,
      scopeKey: scope.scopeKey,
      plan: scope.billingPlan,
      maxPerDay: max,
    });
    logger.warn(
      {
        event: 'poll.campaign_attribution_shed',
        pollId: args.pollId,
        scope: scope.scopeKey,
        code: 'USAGE_LIMIT_CAMPAIGN_ATTRIBUTION',
        max_per_day: max,
        plan: scope.billingPlan,
      },
      'campaign UTM attribution increment skipped: workspace daily cap',
    );
    observeIntegrationEvent('campaign_attribution_shed');
  }
  return ok;
}

async function recordCampaignAttributionShed(args: {
  creatorUserId: number | null | undefined;
  pollId: string;
  scopeKey: string;
  plan: string;
  maxPerDay: number;
}): Promise<void> {
  const workspaceUserId =
    args.creatorUserId != null && Number.isFinite(args.creatorUserId) && args.creatorUserId > 0
      ? args.creatorUserId
      : null;
  if (workspaceUserId == null) return;
  try {
    await AuditLog.create({
      action: CAMPAIGN_ATTRIBUTION_SHED_AUDIT_ACTION,
      actor: `workspace:${workspaceUserId}`,
      target: args.pollId,
      details: {
        workspace_user_id: workspaceUserId,
        scope_key: args.scopeKey,
        plan: args.plan,
        max_per_day: args.maxPerDay,
      },
    });
  } catch (err: unknown) {
    logger.warn(
      {
        event: 'billing.campaign_attribution_meter.write_failed',
        err,
        pollId: args.pollId,
        workspaceUserId,
      },
      'failed to record campaign attribution shed metering row',
    );
  }
}

export function readCampaignAttributionDayMeter(
  scopeKey: string,
  billingPlan: string,
): { current: number; max: number; metered: boolean } {
  const maxPlan = maxCampaignAttributionIncrementsPerUtcDayForBillingPlan(billingPlan);
  const metered = maxPlan < Number.MAX_SAFE_INTEGER / 2;
  if (!metered) {
    return { current: 0, max: maxPlan, metered: false };
  }
  const day = utcDayKey(Date.now());
  pruneBuckets(day);
  const key = meterKey(scopeKey, day);
  return { current: buckets.get(key) ?? 0, max: maxPlan, metered: true };
}
