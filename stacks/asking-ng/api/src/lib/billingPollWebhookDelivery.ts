import Poll from '../model/Poll';
import User from '../models/user.sequelize';
import { findBillingPlanAndRoleForVoteQuota } from '../controller/self/self.repository';
import AuditLog from '../models/auditlog.sequelize';
import { maxOutboundPollWebhookDeliveriesPerMinuteForBillingPlan } from './billingLimits';
import { recordPollWebhookDeliveryTelemetry } from './pollWebhookDeliveryTelemetry';
import { appEnv } from './env';
import { logger } from './logger';
import { observeIntegrationEvent } from './metrics';

const buckets = new Map<string, number>();
export const POLL_WEBHOOK_DELIVERY_SHED_AUDIT_ACTION = 'usage.poll_webhook_delivery_shed';

/** Test-only: clears in-memory webhook delivery counters. */
export function resetPollWebhookDeliveryMeterForTests(): void {
  buckets.clear();
}

/** Scope key for the signed-in user's default billing workspace (`w:{id}` or `u:{userId}` fallback). */
export async function resolveWebhookDeliveryScopeKeyForSignedInUser(userId: number): Promise<string | null> {
  const row = await User.findByPk(userId, { attributes: ['defaultWorkspaceId'] });
  if (!row) return null;
  const def = row.get('defaultWorkspaceId') as number | null | undefined;
  if (def != null && def > 0) return `w:${def}`;
  return `u:${userId}`;
}

/** Current UTC-minute counter vs plan cap (in-process; resets on API restart). */
export function readPollWebhookDeliveryMeterForScope(
  scopeKey: string,
  billingPlan: string,
): { current: number; max: number; metered: boolean } {
  const maxPlan = maxOutboundPollWebhookDeliveriesPerMinuteForBillingPlan(billingPlan);
  const metered = maxPlan < Number.MAX_SAFE_INTEGER / 2;
  if (!metered) {
    return { current: 0, max: maxPlan, metered: false };
  }
  const min = utcMinuteEpoch(Date.now());
  pruneBuckets(min);
  const key = `${scopeKey}:${min}`;
  return { current: buckets.get(key) ?? 0, max: maxPlan, metered: true };
}

function utcMinuteEpoch(ms: number): number {
  return Math.floor(ms / 60_000);
}

function pruneBuckets(nowMin: number): void {
  for (const k of buckets.keys()) {
    const idx = k.lastIndexOf(':');
    if (idx <= 0) continue;
    const m = Number(k.slice(idx + 1));
    if (!Number.isFinite(m) || m < nowMin - 2) {
      buckets.delete(k);
    }
  }
}

/**
 * Stable scope for metering: workspace id when known, else `user:{creatorId}` for legacy rows without workspace.
 */
export async function resolvePollWebhookDeliveryScope(args: {
  pollId: string;
  creatorUserId: number | null | undefined;
}): Promise<{ scopeKey: string; billingPlan: string; role: string | null } | null> {
  const raw = args.pollId?.trim();
  const cid = args.creatorUserId;
  if (!raw || cid == null || !Number.isFinite(cid) || cid <= 0) return null;

  const { billingPlan, role } = await findBillingPlanAndRoleForVoteQuota({
    pollId: raw,
    creatorUserId: cid,
  });

  const poll = await Poll.findByPk(raw, { attributes: ['workspaceId'] });
  const wid = poll?.get('workspaceId') as number | null | undefined;
  if (wid != null && wid > 0) {
    return { scopeKey: `w:${wid}`, billingPlan, role };
  }

  const userRow = await User.findByPk(cid, { attributes: ['defaultWorkspaceId'] });
  const def = userRow?.get('defaultWorkspaceId') as number | null | undefined;
  if (def != null && def > 0) {
    return { scopeKey: `w:${def}`, billingPlan, role };
  }

  return { scopeKey: `u:${cid}`, billingPlan, role };
}

/**
 * When {@link appEnv.billingEnforceLimits} is on, counts delivery **attempts** per scope per UTC minute.
 * Returns false when the cap is exceeded (caller should skip enqueue and log).
 */
export function takePollWebhookDeliverySlot(scopeKey: string, billingPlan: string): boolean {
  const max = maxOutboundPollWebhookDeliveriesPerMinuteForBillingPlan(billingPlan);
  if (max >= Number.MAX_SAFE_INTEGER / 2) return true;

  const min = utcMinuteEpoch(Date.now());
  pruneBuckets(min);
  const key = `${scopeKey}:${min}`;
  const next = (buckets.get(key) ?? 0) + 1;
  if (next > max) {
    return false;
  }
  buckets.set(key, next);
  return true;
}

export async function takePollWebhookDeliveryForPoll(args: {
  pollId: string;
  creatorUserId: number | null | undefined;
}): Promise<boolean> {
  if (!appEnv.billingEnforceLimits) return true;
  const scope = await resolvePollWebhookDeliveryScope({
    pollId: args.pollId,
    creatorUserId: args.creatorUserId,
  });
  if (!scope) return true;
  if (scope.role === 'superadmin') return true;

  const ok = takePollWebhookDeliverySlot(scope.scopeKey, scope.billingPlan);
  if (!ok) {
    const max = maxOutboundPollWebhookDeliveriesPerMinuteForBillingPlan(scope.billingPlan);
    recordPollWebhookDeliveryTelemetry('shed');
    await recordPollWebhookDeliveryShed({
      creatorUserId: args.creatorUserId,
      pollId: args.pollId,
      scopeKey: scope.scopeKey,
      plan: scope.billingPlan,
      maxPerMinute: max,
    });
    logger.warn(
      {
        event: 'poll.webhook.delivery_shed',
        pollId: args.pollId,
        scope: scope.scopeKey,
        code: 'USAGE_LIMIT_POLL_WEBHOOK_DELIVERY',
        max_per_minute: max,
        plan: scope.billingPlan,
      },
      'poll webhook delivery skipped: workspace outbound webhook rate cap',
    );
    observeIntegrationEvent('poll_webhook_delivery_shed');
  }
  return ok;
}

async function recordPollWebhookDeliveryShed(args: {
  creatorUserId: number | null | undefined;
  pollId: string;
  scopeKey: string;
  plan: string;
  maxPerMinute: number;
}): Promise<void> {
  const workspaceUserId =
    args.creatorUserId != null && Number.isFinite(args.creatorUserId) && args.creatorUserId > 0
      ? args.creatorUserId
      : null;
  if (workspaceUserId == null) return;
  try {
    await AuditLog.create({
      action: POLL_WEBHOOK_DELIVERY_SHED_AUDIT_ACTION,
      actor: `workspace:${workspaceUserId}`,
      target: args.pollId,
      details: {
        workspace_user_id: workspaceUserId,
        scope_key: args.scopeKey,
        plan: args.plan,
        max_per_minute: args.maxPerMinute,
      },
    });
  } catch (err: unknown) {
    logger.warn(
      { event: 'billing.poll_webhook_delivery_meter.write_failed', err, pollId: args.pollId, workspaceUserId },
      'failed to record poll webhook delivery shed metering row',
    );
  }
}
