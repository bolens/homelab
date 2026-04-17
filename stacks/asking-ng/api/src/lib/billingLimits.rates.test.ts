import { describe, expect, it } from 'vitest';
import {
  hasExtendedRetentionForBillingPlan,
  hasModerationAutomationForBillingPlan,
  hasForensicReplayForBillingPlan,
  hasWebhookAutomationForBillingPlan,
  hasVoteHeatmapForBillingPlan,
  maxAuthenticatedRestBurstPerMinuteForBillingPlan,
  maxAuthenticatedRestSustainedPerMinuteForBillingPlan,
  maxCampaignAttributionIncrementsPerUtcDayForBillingPlan,
  maxOutboundPollWebhookDeliveriesPerMinuteForBillingPlan,
} from './billingLimits';

describe('authenticated REST rate helpers', () => {
  it('maps sustained per minute by tier', () => {
    expect(maxAuthenticatedRestSustainedPerMinuteForBillingPlan('free')).toBe(120);
    expect(maxAuthenticatedRestSustainedPerMinuteForBillingPlan('cloud-team')).toBe(600);
    expect(maxAuthenticatedRestSustainedPerMinuteForBillingPlan('cloud-pro')).toBe(3000);
    expect(maxAuthenticatedRestSustainedPerMinuteForBillingPlan('selfhost-pro')).toBe(10_000);
  });

  it('uses ~2× sustained burst capped for store safety', () => {
    expect(maxAuthenticatedRestBurstPerMinuteForBillingPlan('free')).toBe(240);
    expect(maxAuthenticatedRestBurstPerMinuteForBillingPlan('cloud-pro')).toBe(6000);
  });

  it('maps outbound poll webhook delivery attempts per minute', () => {
    expect(maxOutboundPollWebhookDeliveriesPerMinuteForBillingPlan('free')).toBe(30);
    expect(maxOutboundPollWebhookDeliveriesPerMinuteForBillingPlan('cloud-team')).toBe(300);
    expect(maxOutboundPollWebhookDeliveriesPerMinuteForBillingPlan('cloud-pro')).toBe(2000);
  });

  it('maps campaign attribution increments per UTC day', () => {
    expect(maxCampaignAttributionIncrementsPerUtcDayForBillingPlan('free')).toBe(100);
    expect(maxCampaignAttributionIncrementsPerUtcDayForBillingPlan('cloud-team')).toBe(5000);
    expect(maxCampaignAttributionIncrementsPerUtcDayForBillingPlan('cloud-pro')).toBe(50_000);
  });

  it('gates premium forensic/heatmap features by plan', () => {
    expect(hasForensicReplayForBillingPlan('free')).toBe(false);
    expect(hasVoteHeatmapForBillingPlan('free')).toBe(false);
    expect(hasForensicReplayForBillingPlan('cloud-team')).toBe(true);
    expect(hasVoteHeatmapForBillingPlan('cloud-team')).toBe(true);
    expect(hasModerationAutomationForBillingPlan('free')).toBe(false);
    expect(hasModerationAutomationForBillingPlan('cloud-team')).toBe(true);
    expect(hasWebhookAutomationForBillingPlan('free')).toBe(false);
    expect(hasWebhookAutomationForBillingPlan('cloud-team')).toBe(true);
    expect(hasExtendedRetentionForBillingPlan('free')).toBe(false);
    expect(hasExtendedRetentionForBillingPlan('cloud-team')).toBe(true);
  });
});
