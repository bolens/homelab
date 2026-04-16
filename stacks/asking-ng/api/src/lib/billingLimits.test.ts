import { describe, expect, it } from 'vitest';
import {
  maxActivePollsForBillingPlan,
  maxDataExportsPerDayForBillingPlan,
  maxVotesPerMonthForBillingPlan,
  maxWsFanoutMessagesPerSecondForBillingPlan,
  maxWsSubscribersPerPollForBillingPlan,
  normalizeBillingPlan,
  utcCalendarDayBounds,
  utcCalendarMonthBounds,
} from './billingLimits';

describe('billingLimits', () => {
  it('normalizeBillingPlan maps known tiers and defaults unknown to free', () => {
    expect(normalizeBillingPlan('cloud-pro')).toBe('cloud-pro');
    expect(normalizeBillingPlan('CLOUD-TEAM')).toBe('cloud-team');
    expect(normalizeBillingPlan('nope')).toBe('free');
    expect(normalizeBillingPlan(undefined)).toBe('free');
  });

  it('maxActivePollsForBillingPlan matches packaging table v1', () => {
    expect(maxActivePollsForBillingPlan('free')).toBe(20);
    expect(maxActivePollsForBillingPlan('cloud-team')).toBe(250);
    expect(maxActivePollsForBillingPlan('cloud-pro')).toBe(2000);
    expect(maxActivePollsForBillingPlan('selfhost-pro')).toBe(2000);
    expect(maxActivePollsForBillingPlan('enterprise-custom')).toBe(Number.MAX_SAFE_INTEGER);
  });

  it('maxVotesPerMonthForBillingPlan matches packaging table v1', () => {
    expect(maxVotesPerMonthForBillingPlan('free')).toBe(50_000);
    expect(maxVotesPerMonthForBillingPlan('cloud-team')).toBe(1_000_000);
    expect(maxVotesPerMonthForBillingPlan('cloud-pro')).toBe(10_000_000);
    expect(maxVotesPerMonthForBillingPlan('selfhost-pro')).toBe(Number.MAX_SAFE_INTEGER);
    expect(maxVotesPerMonthForBillingPlan('enterprise-custom')).toBe(Number.MAX_SAFE_INTEGER);
  });

  it('utcCalendarMonthBounds covers full UTC month', () => {
    const { start, endExclusive } = utcCalendarMonthBounds(Date.UTC(2026, 3, 15, 12, 0, 0));
    expect(start.toISOString()).toBe('2026-04-01T00:00:00.000Z');
    expect(endExclusive.toISOString()).toBe('2026-05-01T00:00:00.000Z');
  });

  it('maxWsSubscribersPerPollForBillingPlan matches packaging table v1', () => {
    expect(maxWsSubscribersPerPollForBillingPlan('free')).toBe(100);
    expect(maxWsSubscribersPerPollForBillingPlan('cloud-team')).toBe(2000);
    expect(maxWsSubscribersPerPollForBillingPlan('cloud-pro')).toBe(15_000);
    expect(maxWsSubscribersPerPollForBillingPlan('selfhost-pro')).toBe(Number.MAX_SAFE_INTEGER);
    expect(maxWsSubscribersPerPollForBillingPlan('enterprise-custom')).toBe(Number.MAX_SAFE_INTEGER);
  });

  it('maxDataExportsPerDayForBillingPlan matches packaging table v1', () => {
    expect(maxDataExportsPerDayForBillingPlan('free')).toBe(3);
    expect(maxDataExportsPerDayForBillingPlan('cloud-team')).toBe(25);
    expect(maxDataExportsPerDayForBillingPlan('cloud-pro')).toBe(200);
    expect(maxDataExportsPerDayForBillingPlan('selfhost-pro')).toBe(Number.MAX_SAFE_INTEGER);
  });

  it('utcCalendarDayBounds spans one UTC day', () => {
    const { start, endExclusive } = utcCalendarDayBounds(Date.UTC(2026, 3, 15, 22, 30, 0));
    expect(start.toISOString()).toBe('2026-04-15T00:00:00.000Z');
    expect(endExclusive.toISOString()).toBe('2026-04-16T00:00:00.000Z');
  });

  it('maxWsFanoutMessagesPerSecondForBillingPlan matches packaging table v1', () => {
    expect(maxWsFanoutMessagesPerSecondForBillingPlan('free')).toBe(30);
    expect(maxWsFanoutMessagesPerSecondForBillingPlan('cloud-team')).toBe(200);
    expect(maxWsFanoutMessagesPerSecondForBillingPlan('cloud-pro')).toBe(1500);
    expect(maxWsFanoutMessagesPerSecondForBillingPlan('selfhost-pro')).toBe(Number.MAX_SAFE_INTEGER);
  });
});
