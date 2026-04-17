import AuditLog from '../models/auditlog.sequelize';
import { logger } from './logger';

/** Audit action when an authenticated user hits tier HTTP burst rate limits (`USAGE_LIMIT_API_RATE`). */
export const API_RATE_LIMIT_AUDIT_ACTION = 'usage.api_rate_limited';

function truncateRoute(raw: string | undefined): string {
  const s = typeof raw === 'string' ? raw.trim() : '';
  if (!s) return 'unknown';
  return s.length > 512 ? `${s.slice(0, 509)}...` : s;
}

/**
 * Best-effort ledger row for customer-visible usage (`GET /profile/billing` → `usage.usageLedger`).
 * Fires once per request that exceeds the global rate limit when `BILLING_ENFORCE_LIMITS` and a user session apply.
 */
export async function recordBillingApiRateLimited(args: {
  userId: number;
  billingPlan: string;
  max: number;
  route: string | undefined;
}): Promise<void> {
  try {
    await AuditLog.create({
      action: API_RATE_LIMIT_AUDIT_ACTION,
      actor: `workspace:${args.userId}`,
      target: truncateRoute(args.route),
      details: {
        workspace_user_id: args.userId,
        plan: args.billingPlan,
        max_per_window: args.max,
      },
    });
  } catch (err: unknown) {
    logger.warn(
      { event: 'billing.api_rate_limit_meter.write_failed', err, userId: args.userId },
      'failed to record API rate limit metering row',
    );
  }
}
