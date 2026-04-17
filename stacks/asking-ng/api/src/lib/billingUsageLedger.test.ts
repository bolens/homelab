import { afterEach, describe, expect, it, vi } from 'vitest';

const { mockQuery } = vi.hoisted(() => ({
  mockQuery: vi.fn(),
}));

vi.mock('../connections', () => ({
  default: {
    query: (...args: unknown[]) => mockQuery(...args),
    define: vi.fn(() => ({})),
  },
}));

vi.mock('./billingExportQuota', () => ({
  DATA_EXPORT_AUDIT_ACTION: 'usage.data_export',
}));

vi.mock('./billingCampaignAttributionQuota', () => ({
  CAMPAIGN_ATTRIBUTION_SHED_AUDIT_ACTION: 'usage.campaign_attribution_shed',
}));

vi.mock('./billingPollWebhookDelivery', () => ({
  POLL_WEBHOOK_DELIVERY_SHED_AUDIT_ACTION: 'usage.poll_webhook_delivery_shed',
}));

vi.mock('./billingApiRateLimitLedger', () => ({
  API_RATE_LIMIT_AUDIT_ACTION: 'usage.api_rate_limited',
}));

vi.mock('./billingWsFanoutLedger', () => ({
  WS_FANOUT_SHED_AUDIT_ACTION: 'usage.ws_fanout_shed',
}));

describe('countBillingUsageActionsForWorkspaceUtcDay', () => {
  afterEach(() => {
    vi.resetModules();
    mockQuery.mockReset();
  });

  it('returns per-action UTC-day counts', async () => {
    mockQuery.mockResolvedValue([
      { action: 'usage.data_export', amount: 7 },
      { action: 'usage.campaign_attribution_shed', amount: 3 },
      { action: 'usage.poll_webhook_delivery_shed', amount: 2 },
      { action: 'usage.api_rate_limited', amount: 4 },
      { action: 'usage.ws_fanout_shed', amount: 5 },
    ]);
    const { countBillingUsageActionsForWorkspaceUtcDay } = await import('./billingUsageLedger');
    await expect(
      countBillingUsageActionsForWorkspaceUtcDay({ workspaceUserId: 42 }),
    ).resolves.toEqual({
      dataExport: 7,
      campaignAttributionShed: 3,
      pollWebhookDeliveryShed: 2,
      apiRateLimited: 4,
      wsFanoutShed: 5,
    });
  });

  it('defaults to zeros when rows are missing', async () => {
    mockQuery.mockResolvedValue([]);
    const { countBillingUsageActionsForWorkspaceUtcDay } = await import('./billingUsageLedger');
    await expect(
      countBillingUsageActionsForWorkspaceUtcDay({ workspaceUserId: 42 }),
    ).resolves.toEqual({
      dataExport: 0,
      campaignAttributionShed: 0,
      pollWebhookDeliveryShed: 0,
      apiRateLimited: 0,
      wsFanoutShed: 0,
    });
  });
});
