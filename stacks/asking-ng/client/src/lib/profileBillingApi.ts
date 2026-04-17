import { isApiFetchError } from '../http';

/** Near-cap hints from `GET /profile/billing` (80% / 95% of max). */
export type BillingUsageWarningsPayload = {
  activePolls?: '80' | '95';
  votesThisMonth?: '80' | '95';
  dataExports?: '80' | '95';
  pollWebhooksThisUtcMinute?: '80' | '95';
  campaignAttribution?: '80' | '95';
};

/** Shape of `GET /profile/billing` (extends over time). */
export type ProfileBillingApiPayload = {
  polar?: {
    customerPortalUrl?: string | null;
    checkoutCloudTeamUrl?: string | null;
    checkoutCloudProUrl?: string | null;
  };
  billing?: {
    plan?: string;
    pastDue?: boolean;
    subscriptionStatus?: string;
    selfhostProLicense?: {
      status?: 'unknown' | 'active' | 'grace' | 'expired';
      validUntilMs?: number | null;
      lastVerifiedMs?: number | null;
      graceUntilMs?: number | null;
    };
  };
  usage?: {
    limitsEnforced?: boolean;
    usageLedger?: Array<{
      ts: string;
      meter:
        | 'data_exports'
        | 'campaign_attribution'
        | 'poll_webhook_delivery'
        | 'api_rate_limit'
        | 'ws_fanout';
      amount: number;
      unit: 'job' | 'increment' | 'delivery' | 'hit';
      scope: 'workspace';
      action:
        | 'usage.data_export'
        | 'usage.campaign_attribution_shed'
        | 'usage.poll_webhook_delivery_shed'
        | 'usage.api_rate_limited'
        | 'usage.ws_fanout_shed';
      ref?: string | null;
    }>;
    usageLedgerDaily?: Array<{
      dayUtc: string;
      meter:
        | 'data_exports'
        | 'campaign_attribution'
        | 'poll_webhook_delivery'
        | 'api_rate_limit'
        | 'ws_fanout';
      amount: number;
      unit: 'job' | 'increment' | 'delivery' | 'hit';
      scope: 'workspace';
      action:
        | 'usage.data_export'
        | 'usage.campaign_attribution_shed'
        | 'usage.poll_webhook_delivery_shed'
        | 'usage.api_rate_limited'
        | 'usage.ws_fanout_shed';
    }>;
    usageReconcile?: {
      generatedAt: string;
      checks: Array<{
        meter:
          | 'data_exports'
          | 'campaign_attribution'
          | 'poll_webhook_delivery'
          | 'api_rate_limit'
          | 'ws_fanout';
        window: 'utc_day';
        derived: number | null;
        raw: number | null;
        status: 'ok' | 'mismatch' | 'unavailable';
      }>;
    };
    activePolls?: number;
    maxActivePolls?: number;
    votesThisMonth?: number;
    maxVotesPerMonth?: number;
    maxWsSubscribersPerPoll?: number;
    exportsToday?: number;
    maxExportsPerDay?: number;
    maxPollLiveFanoutPerSec?: number;
    webhookDeliveriesThisUtcMinute?: number;
    maxWebhookDeliveriesPerUtcMinute?: number;
    campaignAttributionIncrementsToday?: number;
    maxCampaignAttributionPerUtcDay?: number;
    warnings?: BillingUsageWarningsPayload;
  };
};

/** Best upgrade URL for PLAN_LIMIT_* errors using billing profile links. */
export function billingUpgradeUrlForRequiredPlan(
  data: ProfileBillingApiPayload | undefined,
  requiredPlan: string | null | undefined,
): string | null {
  const p = (requiredPlan ?? '').trim().toLowerCase();
  if (p === 'cloud-pro') {
    const pro = data?.polar?.checkoutCloudProUrl;
    if (typeof pro === 'string' && pro.trim() !== '') return pro.trim();
  }
  if (p === 'cloud-team' || p === 'cloud-pro') {
    const team = data?.polar?.checkoutCloudTeamUrl;
    if (typeof team === 'string' && team.trim() !== '') return team.trim();
  }
  const portal = data?.polar?.customerPortalUrl;
  if (typeof portal === 'string' && portal.trim() !== '') return portal.trim();
  return null;
}

export function billingUpgradeHintFromError(
  err: unknown,
  billingData: ProfileBillingApiPayload | undefined,
): { url: string | null; isLicenseRenewal: boolean } {
  const usageLimitUpgradeRequiredPlan = (currentPlanRaw: string | undefined): string | null => {
    const currentPlan = (currentPlanRaw ?? '').trim().toLowerCase();
    if (currentPlan === 'free' || currentPlan === '') return 'cloud-team';
    if (currentPlan === 'cloud-team') return 'cloud-pro';
    return null;
  };
  if (
    !isApiFetchError(err) ||
    (!err.errorCode?.startsWith('PLAN_LIMIT_') &&
      !err.errorCode?.startsWith('USAGE_LIMIT_') &&
      err.errorCode !== 'BILLING_LICENSE_EXPIRED')
  ) {
    return { url: null, isLicenseRenewal: false };
  }
  const details =
    err.details && typeof err.details === 'object' && !Array.isArray(err.details)
      ? (err.details as Record<string, unknown>)
      : null;
  const requiredPlanFromDetails =
    typeof details?.required_plan === 'string' ? details.required_plan : null;
  const requiredPlan =
    requiredPlanFromDetails ??
    (err.errorCode?.startsWith('USAGE_LIMIT_')
      ? usageLimitUpgradeRequiredPlan(billingData?.billing?.plan)
      : null);
  return {
    url: billingUpgradeUrlForRequiredPlan(billingData, requiredPlan),
    isLicenseRenewal: err.errorCode === 'BILLING_LICENSE_EXPIRED',
  };
}

export function billingUsageAtCap(data: ProfileBillingApiPayload | undefined): boolean {
  const u = data?.usage;
  if (!u?.limitsEnforced) return false;
  const cur = u.activePolls;
  const max = u.maxActivePolls;
  if (typeof cur !== 'number' || typeof max !== 'number') return false;
  if (max >= Number.MAX_SAFE_INTEGER / 2) return false;
  return cur >= max;
}

/** Worst threshold from `usage.warnings` for banner styling (95 beats 80). */
export type BillingUsageWarningSeverity = '80' | '95';

/** Past-due subscription: show pay/update CTA when portal URL is configured. */
export function billingPastDueBannerPayload(
  data: ProfileBillingApiPayload | undefined,
): { portalUrl: string } | null {
  if (!data?.billing?.pastDue) return null;
  const url = data.polar?.customerPortalUrl;
  if (typeof url !== 'string' || url.trim() === '') return null;
  return { portalUrl: url.trim() };
}

export function billingUsageWarningSeverity(
  data: ProfileBillingApiPayload | undefined,
): BillingUsageWarningSeverity | null {
  const u = data?.usage;
  if (!u?.limitsEnforced) return null;
  const w = u.warnings;
  if (!w) return null;
  if (
    w.activePolls === '95' ||
    w.votesThisMonth === '95' ||
    w.dataExports === '95' ||
    w.pollWebhooksThisUtcMinute === '95' ||
    w.campaignAttribution === '95'
  ) {
    return '95';
  }
  if (
    w.activePolls === '80' ||
    w.votesThisMonth === '80' ||
    w.dataExports === '80' ||
    w.pollWebhooksThisUtcMinute === '80' ||
    w.campaignAttribution === '80'
  ) {
    return '80';
  }
  return null;
}

export type BillingExportReminder = {
  current: number;
  max: number;
  remaining: number;
  atCap: boolean;
  nearCap: BillingUsageWarningSeverity | null;
};

/** Export reminder payload for downgrade-safe UX nudges. */
export function billingExportReminder(
  data: ProfileBillingApiPayload | undefined,
): BillingExportReminder | null {
  const u = data?.usage;
  if (!u?.limitsEnforced) return null;
  const current = u.exportsToday;
  const max = u.maxExportsPerDay;
  if (typeof current !== 'number' || typeof max !== 'number') return null;
  if (!Number.isFinite(current) || !Number.isFinite(max) || max <= 0) return null;
  if (max >= Number.MAX_SAFE_INTEGER / 2) return null;
  const warn = u.warnings?.dataExports;
  const nearCap: BillingUsageWarningSeverity | null =
    warn === '95' || warn === '80'
      ? warn
      : current / max >= 0.95
        ? '95'
        : current / max >= 0.8
          ? '80'
          : null;
  return {
    current,
    max,
    remaining: Math.max(0, max - current),
    atCap: current >= max,
    nearCap,
  };
}
