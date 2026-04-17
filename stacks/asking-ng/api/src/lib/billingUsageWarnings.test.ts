import { describe, expect, it } from 'vitest';
import { buildBillingUsageWarnings } from './billingUsageWarnings';

describe('buildBillingUsageWarnings', () => {
  it('returns undefined when all meters are low', () => {
    expect(
      buildBillingUsageWarnings({
        activePolls: 10,
        maxActivePolls: 20,
        votesThisMonth: 1000,
        maxVotesPerMonth: 50_000,
        exportsToday: 1,
        maxExportsPerDay: 3,
      }),
    ).toBeUndefined();
  });

  it('flags 80% tier for active polls', () => {
    expect(
      buildBillingUsageWarnings({
        activePolls: 17,
        maxActivePolls: 20,
        votesThisMonth: 0,
        maxVotesPerMonth: 50_000,
        exportsToday: 0,
        maxExportsPerDay: 3,
      }),
    ).toEqual({ activePolls: '80' });
  });

  it('flags 95% tier over 80% for votes', () => {
    expect(
      buildBillingUsageWarnings({
        activePolls: 0,
        maxActivePolls: 20,
        votesThisMonth: 48_000,
        maxVotesPerMonth: 50_000,
        exportsToday: 0,
        maxExportsPerDay: 3,
      }),
    ).toEqual({ votesThisMonth: '95' });
  });

  it('flags 80% for outbound poll webhook deliveries this UTC minute', () => {
    expect(
      buildBillingUsageWarnings({
        activePolls: 0,
        maxActivePolls: 20,
        votesThisMonth: 0,
        maxVotesPerMonth: 50_000,
        exportsToday: 0,
        maxExportsPerDay: 3,
        pollWebhookDeliveriesThisUtcMinute: 25,
        maxPollWebhookDeliveriesPerUtcMinute: 30,
      }),
    ).toEqual({ pollWebhooksThisUtcMinute: '80' });
  });

  it('flags 95% for campaign attribution increments today', () => {
    expect(
      buildBillingUsageWarnings({
        activePolls: 0,
        maxActivePolls: 20,
        votesThisMonth: 0,
        maxVotesPerMonth: 50_000,
        exportsToday: 0,
        maxExportsPerDay: 3,
        campaignAttributionIncrementsToday: 96,
        maxCampaignAttributionPerUtcDay: 100,
      }),
    ).toEqual({ campaignAttribution: '95' });
  });
});
