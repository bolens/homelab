/**
 * Numeric caps from repo `docs/MONETIZATION-AND-PACKAGING.md` (v1 draft).
 * Enforcement is opt-in via {@link ./env.ts} `BILLING_ENFORCE_LIMITS` so OSS/self-host defaults stay unchanged.
 */

export type KnownBillingPlan =
  | 'free'
  | 'cloud-team'
  | 'cloud-pro'
  | 'selfhost-pro'
  | 'enterprise-custom';

export function normalizeBillingPlan(raw: string | null | undefined): KnownBillingPlan {
  const s = (raw ?? 'free').trim().toLowerCase();
  if (
    s === 'cloud-team' ||
    s === 'cloud-pro' ||
    s === 'selfhost-pro' ||
    s === 'enterprise-custom'
  ) {
    return s;
  }
  return 'free';
}

/** Max non-archived polls a user may own as creator (`creator_user_id`). */
export function maxActivePollsForBillingPlan(plan: string): number {
  const p = normalizeBillingPlan(plan);
  switch (p) {
    case 'free':
      return 20;
    case 'cloud-team':
      return 250;
    case 'cloud-pro':
    case 'selfhost-pro':
      return 2000;
    case 'enterprise-custom':
      return Number.MAX_SAFE_INTEGER;
    default:
      return 20;
  }
}

/** UTC calendar month window for vote metering (aligned with `docs/MONETIZATION-AND-PACKAGING.md`). */
export function utcCalendarMonthBounds(nowMs: number = Date.now()): {
  start: Date;
  endExclusive: Date;
} {
  const d = new Date(nowMs);
  const y = d.getUTCFullYear();
  const m = d.getUTCMonth();
  const startMs = Date.UTC(y, m, 1, 0, 0, 0, 0);
  const endExclusiveMs = Date.UTC(y, m + 1, 1, 0, 0, 0, 0);
  return { start: new Date(startMs), endExclusive: new Date(endExclusiveMs) };
}

/** UTC calendar day window for export metering. */
export function utcCalendarDayBounds(nowMs: number = Date.now()): {
  start: Date;
  endExclusive: Date;
} {
  const d = new Date(nowMs);
  const y = d.getUTCFullYear();
  const m = d.getUTCMonth();
  const day = d.getUTCDate();
  const startMs = Date.UTC(y, m, day, 0, 0, 0, 0);
  const endExclusiveMs = startMs + 86_400_000;
  return { start: new Date(startMs), endExclusive: new Date(endExclusiveMs) };
}

/**
 * Non-quarantined vote **rows** accepted this UTC month across all polls owned by the workspace creator.
 * `selection_mode=multi` counts one per selected option (matching inserts).
 */
export function maxVotesPerMonthForBillingPlan(plan: string): number {
  const p = normalizeBillingPlan(plan);
  switch (p) {
    case 'free':
      return 50_000;
    case 'cloud-team':
      return 1_000_000;
    case 'cloud-pro':
      return 10_000_000;
    case 'selfhost-pro':
    case 'enterprise-custom':
      return Number.MAX_SAFE_INTEGER;
    default:
      return 50_000;
  }
}

/** Concurrent poll live WS subscribers per poll (`GET /ws/poll/:id` room size). */
export function maxWsSubscribersPerPollForBillingPlan(plan: string): number {
  const p = normalizeBillingPlan(plan);
  switch (p) {
    case 'free':
      return 100;
    case 'cloud-team':
      return 2_000;
    case 'cloud-pro':
      return 15_000;
    case 'selfhost-pro':
    case 'enterprise-custom':
      return Number.MAX_SAFE_INTEGER;
    default:
      return 100;
  }
}

/** Outbound poll-live WebSocket payloads per poll per second (server→client fanout). */
export function maxWsFanoutMessagesPerSecondForBillingPlan(plan: string): number {
  const p = normalizeBillingPlan(plan);
  switch (p) {
    case 'free':
      return 30;
    case 'cloud-team':
      return 200;
    case 'cloud-pro':
      return 1500;
    case 'selfhost-pro':
    case 'enterprise-custom':
      return Number.MAX_SAFE_INTEGER;
    default:
      return 30;
  }
}

/** Completed data export jobs per UTC day (poll CSV/JSON + `GET /profile/export`). */
export function maxDataExportsPerDayForBillingPlan(plan: string): number {
  const p = normalizeBillingPlan(plan);
  switch (p) {
    case 'free':
      return 3;
    case 'cloud-team':
      return 25;
    case 'cloud-pro':
      return 200;
    case 'selfhost-pro':
    case 'enterprise-custom':
      return Number.MAX_SAFE_INTEGER;
    default:
      return 3;
  }
}

/**
 * Authenticated REST **sustained** requests per minute (v1 draft in repo monetization docs).
 * Burst allowance uses ~2× sustained in the same rolling window (see {@link maxAuthenticatedRestBurstPerMinuteForBillingPlan}).
 */
export function maxAuthenticatedRestSustainedPerMinuteForBillingPlan(plan: string): number {
  const p = normalizeBillingPlan(plan);
  switch (p) {
    case 'free':
      return 120;
    case 'cloud-team':
      return 600;
    case 'cloud-pro':
      return 3000;
    case 'selfhost-pro':
    case 'enterprise-custom':
      /** High default for self-host / enterprise; operators also tune `HTTP_RATE_LIMIT_*` for anonymous traffic. */
      return 10_000;
    default:
      return 120;
  }
}

const REST_BURST_HARD_CAP = 500_000;

/** ~2× sustained, bounded so in-memory rate-limit stores stay sane. */
export function maxAuthenticatedRestBurstPerMinuteForBillingPlan(plan: string): number {
  const sustained = maxAuthenticatedRestSustainedPerMinuteForBillingPlan(plan);
  const doubled = sustained * 2;
  return Math.min(REST_BURST_HARD_CAP, doubled);
}

/** Outbound signed poll webhook POST **attempts** per workspace per UTC minute (repo monetization draft). */
export function maxOutboundPollWebhookDeliveriesPerMinuteForBillingPlan(plan: string): number {
  const p = normalizeBillingPlan(plan);
  switch (p) {
    case 'free':
      return 30;
    case 'cloud-team':
      return 300;
    case 'cloud-pro':
      return 2000;
    case 'selfhost-pro':
    case 'enterprise-custom':
      return Number.MAX_SAFE_INTEGER;
    default:
      return 30;
  }
}

/**
 * UTM / campaign **attributed** poll view increments (`impressionAttribution` bumps) per billing
 * workspace per **UTC calendar day** (MONETIZATION “Campaign attribution queries / day”).
 */
export function maxCampaignAttributionIncrementsPerUtcDayForBillingPlan(plan: string): number {
  const p = normalizeBillingPlan(plan);
  switch (p) {
    case 'free':
      return 100;
    case 'cloud-team':
      return 5_000;
    case 'cloud-pro':
      return 50_000;
    case 'selfhost-pro':
    case 'enterprise-custom':
      return Number.MAX_SAFE_INTEGER;
    default:
      return 100;
  }
}

/** Premium forensic timeline entitlement (`GET /poll/:id/replay`). */
export function hasForensicReplayForBillingPlan(plan: string): boolean {
  const p = normalizeBillingPlan(plan);
  return p !== 'free';
}

/** Premium vote geo heatmap entitlement (`GET /poll/:id/heatmap`). */
export function hasVoteHeatmapForBillingPlan(plan: string): boolean {
  const p = normalizeBillingPlan(plan);
  return p !== 'free';
}

/** Premium moderation batch automation entitlement (`PUT /poll/:id/moderation/batch`). */
export function hasModerationAutomationForBillingPlan(plan: string): boolean {
  const p = normalizeBillingPlan(plan);
  return p !== 'free';
}

/** Premium webhook automation entitlement (`webhook_targets` on poll create/update). */
export function hasWebhookAutomationForBillingPlan(plan: string): boolean {
  const p = normalizeBillingPlan(plan);
  return p !== 'free';
}

/** Premium extended retention entitlement (`retention_ttl_days` create/update fields). */
export function hasExtendedRetentionForBillingPlan(plan: string): boolean {
  const p = normalizeBillingPlan(plan);
  return p !== 'free';
}
