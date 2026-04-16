import fastify, { type FastifyInstance } from 'fastify';
import { afterEach, describe, expect, it, vi } from 'vitest';

const { mockPolarDeliveryCreate } = vi.hoisted(() => ({
  mockPolarDeliveryCreate: vi.fn().mockResolvedValue(undefined),
}));

const mockFindOneDelivery = vi.fn().mockResolvedValue(null);
const mockCountDelivery = vi.fn().mockResolvedValue(0);

vi.mock('../models/polarWebhookDelivery.sequelize', () => ({
  default: {
    create: (...args: unknown[]) => mockPolarDeliveryCreate(...args),
    findOne: (...args: unknown[]) => mockFindOneDelivery(...args),
    count: (...args: unknown[]) => mockCountDelivery(...args),
  },
}));

describe('Polar billing webhooks', () => {
  afterEach(() => {
    vi.resetModules();
    mockPolarDeliveryCreate.mockClear();
    mockFindOneDelivery.mockClear();
    mockCountDelivery.mockClear();
    mockFindOneDelivery.mockResolvedValue(null);
    mockCountDelivery.mockResolvedValue(0);
    delete process.env.ENABLE_POLAR_WEBHOOKS;
    delete process.env.POLAR_WEBHOOK_SECRET;
  });

  async function loadBillingApp(): Promise<FastifyInstance> {
    vi.resetModules();
    const { fastifyBillingRoutes } = await import('./billing');
    const app = fastify();
    await app.register(fastifyBillingRoutes);
    await app.ready();
    return app;
  }

  it('returns 404 when Polar webhooks are disabled', async () => {
    process.env.ENABLE_POLAR_WEBHOOKS = '';
    process.env.POLAR_WEBHOOK_SECRET = '';
    const app = await loadBillingApp();
    const res = await app.inject({
      method: 'POST',
      url: '/billing/webhooks/polar',
      payload: Buffer.from('{}'),
      headers: { 'content-type': 'application/json' },
    });
    expect(res.statusCode).toBe(404);
    expect(res.json()).toMatchObject({
      error: { code: 'NOT_FOUND' },
    });
    expect(mockPolarDeliveryCreate).not.toHaveBeenCalled();
    await app.close();
  });

  it('returns 503 when enabled without POLAR_WEBHOOK_SECRET', async () => {
    process.env.ENABLE_POLAR_WEBHOOKS = 'true';
    process.env.POLAR_WEBHOOK_SECRET = '';
    const app = await loadBillingApp();
    const res = await app.inject({
      method: 'POST',
      url: '/billing/webhooks/polar',
      payload: Buffer.from('{}'),
      headers: { 'content-type': 'application/json' },
    });
    expect(res.statusCode).toBe(503);
    expect(res.json()).toMatchObject({
      error: { code: 'SERVICE_UNAVAILABLE' },
    });
    expect(mockPolarDeliveryCreate).not.toHaveBeenCalled();
    await app.close();
  });

  it('GET /billing/webhooks/info returns delivery stats when webhooks enabled', async () => {
    process.env.ENABLE_POLAR_WEBHOOKS = 'true';
    process.env.POLAR_WEBHOOK_SECRET = 'secret';
    mockCountDelivery.mockResolvedValue(3);
    const fakeLast = {
      get: (k: string) => {
        if (k === 'eventType') return 'subscription.updated';
        if (k === 'createdAt') return new Date('2026-01-02T00:00:00.000Z');
        return null;
      },
    };
    mockFindOneDelivery.mockResolvedValue(fakeLast);
    const app = await loadBillingApp();
    const res = await app.inject({ method: 'GET', url: '/billing/webhooks/info' });
    expect(res.statusCode).toBe(200);
    expect(res.json()).toMatchObject({
      enabled: true,
      deliveriesStoredCount: 3,
      lastStoredDelivery: {
        eventType: 'subscription.updated',
        receivedAt: '2026-01-02T00:00:00.000Z',
      },
    });
    await app.close();
  });

  it('returns 403 on invalid signature when secret is set', async () => {
    process.env.ENABLE_POLAR_WEBHOOKS = 'true';
    process.env.POLAR_WEBHOOK_SECRET = 'test_secret_which_is_not_base64_but_sdk_may_still_run';
    const app = await loadBillingApp();
    const res = await app.inject({
      method: 'POST',
      url: '/billing/webhooks/polar',
      payload: Buffer.from('{"not":"a real polar event"}'),
      headers: { 'content-type': 'application/json' },
    });
    expect(res.statusCode).toBe(403);
    expect(res.json()).toMatchObject({
      error: { code: 'FORBIDDEN' },
    });
    expect(mockPolarDeliveryCreate).not.toHaveBeenCalled();
    await app.close();
  });
});
