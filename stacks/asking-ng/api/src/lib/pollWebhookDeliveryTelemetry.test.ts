import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  readPollWebhookDeliveryTelemetry,
  recordPollWebhookDeliveryTelemetry,
  resetPollWebhookDeliveryTelemetryForTests,
} from './pollWebhookDeliveryTelemetry';

describe('pollWebhookDeliveryTelemetry', () => {
  beforeEach(() => {
    resetPollWebhookDeliveryTelemetryForTests();
    vi.useRealTimers();
  });

  it('aggregates counters within the requested rolling window', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-04-16T12:00:05.000Z'));
    recordPollWebhookDeliveryTelemetry('attempted');
    recordPollWebhookDeliveryTelemetry('delivered_ok');
    recordPollWebhookDeliveryTelemetry('shed');

    vi.setSystemTime(new Date('2026-04-16T12:01:05.000Z'));
    recordPollWebhookDeliveryTelemetry('attempted');
    recordPollWebhookDeliveryTelemetry('delivered_non_2xx');

    const snapshot = readPollWebhookDeliveryTelemetry(5);
    expect(snapshot).toMatchObject({
      window_minutes: 5,
      attempted: 2,
      delivered_ok: 1,
      delivered_non_2xx: 1,
      delivery_failed: 0,
      shed: 1,
      current_minute_attempted: 1,
      current_minute_shed: 0,
    });
  });

  it('drops counters outside the rolling window', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-04-16T12:00:05.000Z'));
    recordPollWebhookDeliveryTelemetry('attempted');
    recordPollWebhookDeliveryTelemetry('delivery_failed');

    vi.setSystemTime(new Date('2026-04-16T12:20:05.000Z'));
    recordPollWebhookDeliveryTelemetry('attempted');
    recordPollWebhookDeliveryTelemetry('delivered_ok');

    const snapshot = readPollWebhookDeliveryTelemetry(15);
    expect(snapshot).toMatchObject({
      attempted: 1,
      delivered_ok: 1,
      delivery_failed: 0,
      current_minute_attempted: 1,
    });
  });
});
