import type { BillingUsageWarnings } from '../../lib/billingUsageWarnings';
import type {
  BillingUsageLedgerDailyRollupEntry,
  BillingUsageLedgerEntry,
} from '../../lib/billingUsageLedger';
import type { SelfhostProLicenseState } from '../../lib/selfhostProLicense';

type ProfileSummary = {
  id: number;
  homelab-user: string;
  role: string;
  llmGatewayToken: string | null;
  billingPlan: string;
};

export function presentProfile(payload: { user: ProfileSummary }): Record<string, unknown> {
  return {
    user: {
      id: payload.user.id,
      homelab-user: payload.user.homelab-user,
      role: payload.user.role,
      llmGatewayToken: payload.user.llmGatewayToken,
      billingPlan: payload.user.billingPlan,
    },
  };
}

export type PolarBillingUsage = {
  limitsEnforced: boolean;
  /** Recent metered usage rows for customer-visible reconciliation/export checks (latest first). */
  usageLedger?: BillingUsageLedgerEntry[];
  /** Daily UTC rollups by action for quick customer-side reconciliation. */
  usageLedgerDaily?: BillingUsageLedgerDailyRollupEntry[];
  /** Internal meter-vs-ledger checks for support/debug visibility. */
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
  /** Non-quarantined vote rows this UTC calendar month for polls this user owns as creator. */
  votesThisMonth?: number;
  maxVotesPerMonth?: number;
  /** Effective max concurrent WS subscribers per poll you own (`min(env, plan)` when limits enforced). */
  maxWsSubscribersPerPoll?: number;
  /** Completed data export jobs this UTC day (poll exports + profile export) attributed to your workspace. */
  exportsToday?: number;
  maxExportsPerDay?: number;
  /** Server→client poll-live messages per poll per second cap (`min(WS_FANOUT_*, plan)` when limits enforced). */
  maxPollLiveFanoutPerSec?: number;
  /** Outbound signed poll webhook POST attempts in the current UTC minute (in-process meter). */
  webhookDeliveriesThisUtcMinute?: number;
  maxWebhookDeliveriesPerUtcMinute?: number;
  /** UTM / campaign attributed view increments this UTC day (in-process meter). */
  campaignAttributionIncrementsToday?: number;
  maxCampaignAttributionPerUtcDay?: number;
  /** Approaching numeric caps (80% / 95% of max) for dashboard UX. */
  warnings?: BillingUsageWarnings;
};

export type PolarBillingLinks = {
  customerPortalUrl: string | null;
  checkoutCloudTeamUrl: string | null;
  checkoutCloudProUrl: string | null;
  billingPlan: string;
  usage: PolarBillingUsage;
  /** When the default workspace is linked to Polar, surface last known subscription status (e.g. `past_due`). */
  subscription?: { polarStatus: string | null; pastDue: boolean };
  /** Self-host Pro license status surface (phase 1 visibility; enforcement wiring follows). */
  selfhostProLicense?: SelfhostProLicenseState;
};

export function presentPolarBillingLinks(links: PolarBillingLinks): Record<string, unknown> {
  const billing: Record<string, unknown> = { plan: links.billingPlan };
  if (links.subscription) {
    if (links.subscription.polarStatus) {
      billing.subscriptionStatus = links.subscription.polarStatus;
    }
    if (links.subscription.pastDue) {
      billing.pastDue = true;
    }
  }
  if (links.selfhostProLicense) {
    billing.selfhostProLicense = links.selfhostProLicense;
  }
  return {
    polar: {
      customerPortalUrl: links.customerPortalUrl,
      checkoutCloudTeamUrl: links.checkoutCloudTeamUrl,
      checkoutCloudProUrl: links.checkoutCloudProUrl,
    },
    billing,
    usage: links.usage,
  };
}

export function presentPasswordUpdated(): Record<string, unknown> {
  return { message: 'Password updated' };
}

export function presentSelfDeleted(): Record<string, unknown> {
  return { message: 'Account and personal data deleted' };
}
