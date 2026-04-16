import { describe, expect, it } from 'vitest';
import {
  maxAuthenticatedRestBurstPerMinuteForBillingPlan,
  maxAuthenticatedRestSustainedPerMinuteForBillingPlan,
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
});
