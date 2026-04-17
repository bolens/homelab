import fastify, { type FastifyInstance } from 'fastify';
import { afterEach, describe, expect, it, vi } from 'vitest';

const { mockPolarDeliveryCreate, mockValidateEvent, mockApplyPolar } = vi.hoisted(() => ({
  mockPolarDeliveryCreate: vi.fn().mockResolvedValue(undefined),
  mockValidateEvent: vi.fn(),
  mockApplyPolar: vi.fn().mockResolvedValue(undefined),
}));

vi.mock('@polar-sh/sdk/webhooks', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@polar-sh/sdk/webhooks')>();
  return {
    ...actual,
    validateEvent: (...args: unknown[]) =>
      mockValidateEvent(...args) as ReturnType<typeof actual.validateEvent>,
  };
});

vi.mock('../lib/polarSubscriptionApply', () => ({
  applyPolarSubscriptionWebhookEvent: (...args: unknown[]) => mockApplyPolar(...args),
}));

vi.mock('../models/polarWebhookDelivery.sequelize', () => ({
  default: {
    create: (...args: unknown[]) => mockPolarDeliveryCreate(...args),
  },
}));

describe('Polar billing webhooks (entitlements wiring)', () => {
  afterEach(() => {
    vi.resetModules();
    mockPolarDeliveryCreate.mockClear();
    mockValidateEvent.mockReset();
    mockApplyPolar.mockClear();
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

  it('stores verified webhook and applies subscription entitlements', async () => {
    process.env.ENABLE_POLAR_WEBHOOKS = 'true';
    process.env.POLAR_WEBHOOK_SECRET = 'secret';
    mockValidateEvent.mockReturnValue({
      type: 'subscription.active',
      data: {
        id: 'sub_1',
        customerId: 'cus_1',
        productId: 'prod_1',
        status: 'active',
        metadata: {},
      },
    });
    const app = await loadBillingApp();
    const res = await app.inject({
      method: 'POST',
      url: '/billing/webhooks/polar',
      payload: Buffer.from('{}'),
      headers: { 'content-type': 'application/json', 'webhook-id': 'wh_test_1' },
    });
    expect(res.statusCode).toBe(204);
    expect(mockPolarDeliveryCreate).toHaveBeenCalled();
    expect(mockApplyPolar).toHaveBeenCalledWith(
      expect.objectContaining({ type: 'subscription.active' }),
      expect.anything(),
    );
    await app.close();
  });

  it('returns 204 when entitlements apply throws', async () => {
    process.env.ENABLE_POLAR_WEBHOOKS = 'true';
    process.env.POLAR_WEBHOOK_SECRET = 'secret';
    mockValidateEvent.mockReturnValue({
      type: 'subscription.active',
      data: {
        id: 'sub_2',
        customerId: 'cus_2',
        productId: 'prod_2',
        status: 'active',
        metadata: {},
      },
    });
    mockApplyPolar.mockRejectedValueOnce(new Error('db down'));
    const app = await loadBillingApp();
    const res = await app.inject({
      method: 'POST',
      url: '/billing/webhooks/polar',
      payload: Buffer.from('{}'),
      headers: { 'content-type': 'application/json', 'webhook-id': 'wh_test_2' },
    });
    expect(res.statusCode).toBe(204);
    expect(mockApplyPolar).toHaveBeenCalled();
    await app.close();
  });
});
