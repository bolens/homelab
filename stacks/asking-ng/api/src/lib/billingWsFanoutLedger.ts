import AuditLog from '../models/auditlog.sequelize';
import { logger } from './logger';

/** Audit action when poll-live outbound WS fanout is shed due to plan cap (`USAGE_LIMIT_WS_FANOUT`). */
export const WS_FANOUT_SHED_AUDIT_ACTION = 'usage.ws_fanout_shed';

export async function recordBillingWsFanoutShed(args: {
  userId: number;
  billingPlan: string;
  pollId: string;
  cap: number;
}): Promise<void> {
  try {
    await AuditLog.create({
      action: WS_FANOUT_SHED_AUDIT_ACTION,
      actor: `workspace:${args.userId}`,
      target: args.pollId,
      details: {
        workspace_user_id: args.userId,
        plan: args.billingPlan,
        cap_per_sec: args.cap,
      },
    });
  } catch (err: unknown) {
    logger.warn(
      {
        event: 'billing.ws_fanout_shed_meter.write_failed',
        err,
        userId: args.userId,
        pollId: args.pollId,
      },
      'failed to record ws fanout shed metering row',
    );
  }
}
