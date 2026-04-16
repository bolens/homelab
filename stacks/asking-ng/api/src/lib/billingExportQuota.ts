import { QueryTypes } from 'sequelize';
import db from '../connections';
import { findBillingPlanAndRoleByUserId } from '../controller/self/self.repository';
import AuditLog from '../models/auditlog.sequelize';
import { maxDataExportsPerDayForBillingPlan, utcCalendarDayBounds } from './billingLimits';
import { appEnv } from './env';
import { logger } from './logger';

/** Audit rows used to count completed data-export jobs per workspace per UTC day. */
export const DATA_EXPORT_AUDIT_ACTION = 'usage.data_export';

export type DataExportKind = 'poll' | 'self';

export type DailyExportQuotaDenied = { ok: false; max: number; current: number; plan: string };
export type DailyExportQuotaOk = { ok: true };

export async function countCompletedDataExportsForWorkspaceUtcDay(workspaceUserId: number): Promise<number> {
  const { start, endExclusive } = utcCalendarDayBounds();
  const [r] = (await db.query(
    `SELECT COUNT(*)::int AS c
     FROM audit_logs
     WHERE action = :action
       AND (details->>'workspace_user_id')::int = :workspaceUserId
       AND "createdAt" >= :start
       AND "createdAt" < :endExclusive`,
    {
      replacements: {
        action: DATA_EXPORT_AUDIT_ACTION,
        workspaceUserId,
        start,
        endExclusive,
      },
      type: QueryTypes.SELECT,
    },
  )) as Array<{ c: string | number }>;
  return Number(r?.c ?? 0) || 0;
}

export async function checkDailyDataExportQuotaForWorkspace(args: {
  workspaceUserId: number | null;
}): Promise<DailyExportQuotaOk | DailyExportQuotaDenied> {
  if (!appEnv.billingEnforceLimits) return { ok: true };
  const wid = args.workspaceUserId;
  if (wid == null) return { ok: true };

  const { billingPlan, role } = await findBillingPlanAndRoleByUserId(wid);
  if (role === 'superadmin') return { ok: true };

  const max = maxDataExportsPerDayForBillingPlan(billingPlan);
  if (max >= Number.MAX_SAFE_INTEGER / 2) return { ok: true };

  const current = await countCompletedDataExportsForWorkspaceUtcDay(wid);
  if (current >= max) {
    return { ok: false, max, current, plan: billingPlan };
  }
  return { ok: true };
}

export async function recordDataExportJob(args: {
  workspaceUserId: number;
  kind: DataExportKind;
  pollId?: string | null;
}): Promise<void> {
  try {
    await AuditLog.create({
      action: DATA_EXPORT_AUDIT_ACTION,
      actor: `workspace:${args.workspaceUserId}`,
      target: args.kind === 'poll' ? (args.pollId ?? '') : 'profile',
      details: {
        workspace_user_id: args.workspaceUserId,
        kind: args.kind,
        poll_id: args.pollId ?? null,
      },
    });
  } catch (err: unknown) {
    logger.warn(
      { event: 'billing.export_meter.write_failed', err, workspaceUserId: args.workspaceUserId, kind: args.kind },
      'failed to record data export metering row',
    );
  }
}
