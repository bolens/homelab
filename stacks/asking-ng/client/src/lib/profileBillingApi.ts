/** Near-cap hints from `GET /profile/billing` (80% / 95% of max). */
export type BillingUsageWarningsPayload = {
  activePolls?: '80' | '95';
  votesThisMonth?: '80' | '95';
  dataExports?: '80' | '95';
};

/** Shape of `GET /profile/billing` (extends over time). */
export type ProfileBillingApiPayload = {
  polar?: {
    customerPortalUrl?: string | null;
    checkoutCloudTeamUrl?: string | null;
    checkoutCloudProUrl?: string | null;
  };
  billing?: { plan?: string };
  usage?: {
    limitsEnforced?: boolean;
    activePolls?: number;
    maxActivePolls?: number;
    votesThisMonth?: number;
    maxVotesPerMonth?: number;
    maxWsSubscribersPerPoll?: number;
    exportsToday?: number;
    maxExportsPerDay?: number;
    maxPollLiveFanoutPerSec?: number;
    warnings?: BillingUsageWarningsPayload;
  };
};

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

export function billingUsageWarningSeverity(
  data: ProfileBillingApiPayload | undefined,
): BillingUsageWarningSeverity | null {
  const u = data?.usage;
  if (!u?.limitsEnforced) return null;
  const w = u.warnings;
  if (!w) return null;
  if (w.activePolls === '95' || w.votesThisMonth === '95' || w.dataExports === '95') return '95';
  if (w.activePolls === '80' || w.votesThisMonth === '80' || w.dataExports === '80') return '80';
  return null;
}
