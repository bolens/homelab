import { beforeEach, describe, expect, it } from 'vitest';
import {
  resetPollWebhookDeliveryMeterForTests,
  takePollWebhookDeliverySlot,
} from './billingPollWebhookDelivery';

beforeEach(() => {
  resetPollWebhookDeliveryMeterForTests();
});

describe('takePollWebhookDeliverySlot', () => {
  it('allows up to max attempts per UTC minute bucket', () => {
    const scope = 'w:42';
    const plan = 'free'; // 30/min
    for (let i = 0; i < 30; i += 1) {
      expect(takePollWebhookDeliverySlot(scope, plan)).toBe(true);
    }
    expect(takePollWebhookDeliverySlot(scope, plan)).toBe(false);
  });

  it('uses independent buckets per scope key', () => {
    expect(takePollWebhookDeliverySlot('w:1', 'free')).toBe(true);
    expect(takePollWebhookDeliverySlot('w:2', 'free')).toBe(true);
  });
});
