import { describe, expect, it, vi } from 'vitest';

vi.mock('./env', () => ({
  appEnv: {
    polarProductIdCloudTeam: 'prod_team',
    polarProductIdCloudPro: 'prod_pro',
  },
}));

vi.mock('../models/user.sequelize', () => ({
  default: {},
}));

vi.mock('../models/workspace.sequelize', () => ({
  default: {},
}));

import type { Subscription } from '@polar-sh/sdk/models/components/subscription';
import {
  analyzePolarSubscriptionPlan,
  resolveBillingPlanFromPolarProductId,
  subscriptionGrantsPaidPlan,
} from './polarSubscriptionApply';

describe('polarSubscriptionApply helpers', () => {
  it('subscriptionGrantsPaidPlan respects status and revoked', () => {
    expect(subscriptionGrantsPaidPlan('active', 'subscription.active')).toBe(true);
    expect(subscriptionGrantsPaidPlan('trialing', 'subscription.updated')).toBe(true);
    expect(subscriptionGrantsPaidPlan('past_due', 'subscription.updated')).toBe(true);
    expect(subscriptionGrantsPaidPlan('canceled', 'subscription.updated')).toBe(false);
    expect(subscriptionGrantsPaidPlan('active', 'subscription.revoked')).toBe(false);
  });

  it('resolveBillingPlanFromPolarProductId maps env product ids', () => {
    expect(resolveBillingPlanFromPolarProductId('prod_pro')).toBe('cloud-pro');
    expect(resolveBillingPlanFromPolarProductId('prod_team')).toBe('cloud-team');
    expect(resolveBillingPlanFromPolarProductId('unknown')).toBe(null);
  });

  it('analyzePolarSubscriptionPlan maps active + product to paid tier', () => {
    const sub = {
      id: 'sub_1',
      customerId: 'cus_1',
      productId: 'prod_pro',
      status: 'active',
      metadata: {},
    } as Subscription;
    expect(analyzePolarSubscriptionPlan(sub, 'subscription.updated')).toEqual({
      touchBillingPlan: true,
      nextPlan: 'cloud-pro',
      unmappedPaidProduct: false,
    });
  });

  it('analyzePolarSubscriptionPlan downgrades non-paid status', () => {
    const sub = {
      id: 'sub_1',
      customerId: 'cus_1',
      productId: 'prod_pro',
      status: 'canceled',
      metadata: {},
    } as Subscription;
    expect(analyzePolarSubscriptionPlan(sub, 'subscription.updated')).toEqual({
      touchBillingPlan: true,
      nextPlan: 'free',
      unmappedPaidProduct: false,
    });
  });

  it('analyzePolarSubscriptionPlan flags unmapped paid product', () => {
    const sub = {
      id: 'sub_1',
      customerId: 'cus_1',
      productId: 'unknown_sku',
      status: 'active',
      metadata: {},
    } as Subscription;
    expect(analyzePolarSubscriptionPlan(sub, 'subscription.updated')).toEqual({
      touchBillingPlan: false,
      nextPlan: null,
      unmappedPaidProduct: true,
    });
  });
});
