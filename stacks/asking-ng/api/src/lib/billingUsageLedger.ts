import { QueryTypes } from 'sequelize';
import db from '../connections';
import { API_RATE_LIMIT_AUDIT_ACTION } from './billingApiRateLimitLedger';
import { DATA_EXPORT_AUDIT_ACTION } from './billingExportQuota';
import { CAMPAIGN_ATTRIBUTION_SHED_AUDIT_ACTION } from './billingCampaignAttributionQuota';
import { POLL_WEBHOOK_DELIVERY_SHED_AUDIT_ACTION } from './billingPollWebhookDelivery';
import { WS_FANOUT_SHED_AUDIT_ACTION } from './billingWsFanoutLedger';

export type BillingUsageLedgerEntry = {
  ts: string;
  meter: 'data_exports' | 'campaign_attribution' | 'poll_webhook_delivery' | 'api_rate_limit' | 'ws_fanout';
  amount: number;
  unit: 'job' | 'increment' | 'delivery' | 'hit';
  scope: 'workspace';
  action:
    | 'usage.data_export'
    | 'usage.campaign_attribution_shed'
    | 'usage.poll_webhook_delivery_shed'
    | 'usage.api_rate_limited'
    | 'usage.ws_fanout_shed';
  ref: string | null;
};

export type BillingUsageLedgerDailyRollupEntry = {
  dayUtc: string;
  meter: 'data_exports' | 'campaign_attribution' | 'poll_webhook_delivery' | 'api_rate_limit' | 'ws_fanout';
  amount: number;
  unit: 'job' | 'increment' | 'delivery' | 'hit';
  scope: 'workspace';
  action:
    | 'usage.data_export'
    | 'usage.campaign_attribution_shed'
    | 'usage.poll_webhook_delivery_shed'
    | 'usage.api_rate_limited'
    | 'usage.ws_fanout_shed';
};

type UsageAuditRow = {
  action: string;
  target: string | null;
  createdAt: Date | string;
};

type UsageDailyAuditRow = {
  action: string;
  dayUtc: string;
  amount: string | number;
};

type UsageUtcDayCountRow = {
  action: string;
  amount: string | number;
};

const MAX_LEDGER_ROWS = 50;
const DEFAULT_LEDGER_ROWS = 25;
const MAX_DAILY_ROLLUP_DAYS = 31;
const DEFAULT_DAILY_ROLLUP_DAYS = 14;

function normalizeLedgerLimit(limit: number | undefined): number {
  if (typeof limit !== 'number' || !Number.isFinite(limit)) return DEFAULT_LEDGER_ROWS;
  const n = Math.trunc(limit);
  if (n < 1) return 1;
  if (n > MAX_LEDGER_ROWS) return MAX_LEDGER_ROWS;
  return n;
}

function normalizeRollupDays(days: number | undefined): number {
  if (typeof days !== 'number' || !Number.isFinite(days)) return DEFAULT_DAILY_ROLLUP_DAYS;
  const n = Math.trunc(days);
  if (n < 1) return 1;
  if (n > MAX_DAILY_ROLLUP_DAYS) return MAX_DAILY_ROLLUP_DAYS;
  return n;
}

export async function listRecentBillingUsageLedgerForWorkspace(args: {
  workspaceUserId: number;
  limit?: number;
}): Promise<BillingUsageLedgerEntry[]> {
  const limit = normalizeLedgerLimit(args.limit);
  const rows = (await db.query(
    `SELECT action, target, "createdAt"
     FROM audit_logs
     WHERE action IN (:dataExportAction, :campaignAttributionShedAction, :pollWebhookDeliveryShedAction, :apiRateLimitAction, :wsFanoutShedAction)
       AND details->>'workspace_user_id' = :workspaceUserIdText
     ORDER BY "createdAt" DESC
     LIMIT :limit`,
    {
      replacements: {
        dataExportAction: DATA_EXPORT_AUDIT_ACTION,
        campaignAttributionShedAction: CAMPAIGN_ATTRIBUTION_SHED_AUDIT_ACTION,
        pollWebhookDeliveryShedAction: POLL_WEBHOOK_DELIVERY_SHED_AUDIT_ACTION,
        apiRateLimitAction: API_RATE_LIMIT_AUDIT_ACTION,
        wsFanoutShedAction: WS_FANOUT_SHED_AUDIT_ACTION,
        workspaceUserIdText: String(args.workspaceUserId),
        limit,
      },
      type: QueryTypes.SELECT,
    },
  )) as UsageAuditRow[];

  return rows.map((row) => {
    const ref = row.target && row.target.trim() !== '' ? row.target : null;
    if (row.action === CAMPAIGN_ATTRIBUTION_SHED_AUDIT_ACTION) {
      return {
        ts: new Date(row.createdAt).toISOString(),
        meter: 'campaign_attribution',
        amount: 1,
        unit: 'increment',
        scope: 'workspace',
        action: 'usage.campaign_attribution_shed',
        ref,
      };
    }
    if (row.action === POLL_WEBHOOK_DELIVERY_SHED_AUDIT_ACTION) {
      return {
        ts: new Date(row.createdAt).toISOString(),
        meter: 'poll_webhook_delivery',
        amount: 1,
        unit: 'delivery',
        scope: 'workspace',
        action: 'usage.poll_webhook_delivery_shed',
        ref,
      };
    }
    if (row.action === API_RATE_LIMIT_AUDIT_ACTION) {
      return {
        ts: new Date(row.createdAt).toISOString(),
        meter: 'api_rate_limit',
        amount: 1,
        unit: 'hit',
        scope: 'workspace',
        action: 'usage.api_rate_limited',
        ref,
      };
    }
    if (row.action === WS_FANOUT_SHED_AUDIT_ACTION) {
      return {
        ts: new Date(row.createdAt).toISOString(),
        meter: 'ws_fanout',
        amount: 1,
        unit: 'hit',
        scope: 'workspace',
        action: 'usage.ws_fanout_shed',
        ref,
      };
    }
    return {
      ts: new Date(row.createdAt).toISOString(),
      meter: 'data_exports',
      amount: 1,
      unit: 'job',
      scope: 'workspace',
      action: 'usage.data_export',
      ref,
    };
  });
}

export async function listDailyBillingUsageRollupsForWorkspace(args: {
  workspaceUserId: number;
  days?: number;
}): Promise<BillingUsageLedgerDailyRollupEntry[]> {
  const days = normalizeRollupDays(args.days);
  const rows = (await db.query(
    `SELECT action,
            to_char(date_trunc('day', "createdAt" AT TIME ZONE 'UTC'), 'YYYY-MM-DD') AS "dayUtc",
            COUNT(*)::int AS amount
     FROM audit_logs
     WHERE action IN (:dataExportAction, :campaignAttributionShedAction, :pollWebhookDeliveryShedAction, :apiRateLimitAction, :wsFanoutShedAction)
       AND details->>'workspace_user_id' = :workspaceUserIdText
       AND "createdAt" >= (NOW() AT TIME ZONE 'UTC') - (:days * interval '1 day')
     GROUP BY action, "dayUtc"
     ORDER BY "dayUtc" DESC, action ASC`,
    {
      replacements: {
        dataExportAction: DATA_EXPORT_AUDIT_ACTION,
        campaignAttributionShedAction: CAMPAIGN_ATTRIBUTION_SHED_AUDIT_ACTION,
        pollWebhookDeliveryShedAction: POLL_WEBHOOK_DELIVERY_SHED_AUDIT_ACTION,
        apiRateLimitAction: API_RATE_LIMIT_AUDIT_ACTION,
        wsFanoutShedAction: WS_FANOUT_SHED_AUDIT_ACTION,
        workspaceUserIdText: String(args.workspaceUserId),
        days,
      },
      type: QueryTypes.SELECT,
    },
  )) as UsageDailyAuditRow[];

  return rows.map((row) => {
    if (row.action === CAMPAIGN_ATTRIBUTION_SHED_AUDIT_ACTION) {
      return {
        dayUtc: row.dayUtc,
        meter: 'campaign_attribution',
        amount: Number(row.amount) || 0,
        unit: 'increment',
        scope: 'workspace',
        action: 'usage.campaign_attribution_shed',
      };
    }
    if (row.action === POLL_WEBHOOK_DELIVERY_SHED_AUDIT_ACTION) {
      return {
        dayUtc: row.dayUtc,
        meter: 'poll_webhook_delivery',
        amount: Number(row.amount) || 0,
        unit: 'delivery',
        scope: 'workspace',
        action: 'usage.poll_webhook_delivery_shed',
      };
    }
    if (row.action === API_RATE_LIMIT_AUDIT_ACTION) {
      return {
        dayUtc: row.dayUtc,
        meter: 'api_rate_limit',
        amount: Number(row.amount) || 0,
        unit: 'hit',
        scope: 'workspace',
        action: 'usage.api_rate_limited',
      };
    }
    if (row.action === WS_FANOUT_SHED_AUDIT_ACTION) {
      return {
        dayUtc: row.dayUtc,
        meter: 'ws_fanout',
        amount: Number(row.amount) || 0,
        unit: 'hit',
        scope: 'workspace',
        action: 'usage.ws_fanout_shed',
      };
    }
    return {
      dayUtc: row.dayUtc,
      meter: 'data_exports',
      amount: Number(row.amount) || 0,
      unit: 'job',
      scope: 'workspace',
      action: 'usage.data_export',
    };
  });
}

export async function countBillingUsageActionsForWorkspaceUtcDay(args: {
  workspaceUserId: number;
}): Promise<{
  dataExport: number;
  campaignAttributionShed: number;
  pollWebhookDeliveryShed: number;
  apiRateLimited: number;
  wsFanoutShed: number;
}> {
  const rows = (await db.query(
    `SELECT action, COUNT(*)::int AS amount
     FROM audit_logs
     WHERE action IN (:dataExportAction, :campaignAttributionShedAction, :pollWebhookDeliveryShedAction, :apiRateLimitAction, :wsFanoutShedAction)
       AND details->>'workspace_user_id' = :workspaceUserIdText
       AND "createdAt" >= date_trunc('day', NOW() AT TIME ZONE 'UTC')
       AND "createdAt" < date_trunc('day', NOW() AT TIME ZONE 'UTC') + interval '1 day'
     GROUP BY action`,
    {
      replacements: {
        dataExportAction: DATA_EXPORT_AUDIT_ACTION,
        campaignAttributionShedAction: CAMPAIGN_ATTRIBUTION_SHED_AUDIT_ACTION,
        pollWebhookDeliveryShedAction: POLL_WEBHOOK_DELIVERY_SHED_AUDIT_ACTION,
        apiRateLimitAction: API_RATE_LIMIT_AUDIT_ACTION,
        wsFanoutShedAction: WS_FANOUT_SHED_AUDIT_ACTION,
        workspaceUserIdText: String(args.workspaceUserId),
      },
      type: QueryTypes.SELECT,
    },
  )) as UsageUtcDayCountRow[];

  let dataExport = 0;
  let campaignAttributionShed = 0;
  let pollWebhookDeliveryShed = 0;
  let apiRateLimited = 0;
  let wsFanoutShed = 0;
  for (const row of rows) {
    const amount = Number(row.amount) || 0;
    if (row.action === DATA_EXPORT_AUDIT_ACTION) dataExport = amount;
    else if (row.action === CAMPAIGN_ATTRIBUTION_SHED_AUDIT_ACTION) campaignAttributionShed = amount;
    else if (row.action === POLL_WEBHOOK_DELIVERY_SHED_AUDIT_ACTION) pollWebhookDeliveryShed = amount;
    else if (row.action === API_RATE_LIMIT_AUDIT_ACTION) apiRateLimited = amount;
    else if (row.action === WS_FANOUT_SHED_AUDIT_ACTION) wsFanoutShed = amount;
  }
  return { dataExport, campaignAttributionShed, pollWebhookDeliveryShed, apiRateLimited, wsFanoutShed };
}
