import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  getSub: vi.fn(),
  findAll: vi.fn(),
  persist: vi.fn(),
}));

vi.mock('./env', () => ({
  appEnv: {
    polarProductIdCloudTeam: 'prod_team',
    polarProductIdCloudPro: 'prod_pro',
    polarServer: 'production',
    polarAccessToken: 'test-token',
  },
}));

vi.mock('./polarApiClient', () => ({
  createPolarServerClient: () => ({
    subscriptions: { get: mocks.getSub },
  }),
}));

vi.mock('../models/user.sequelize', () => ({
  default: {},
}));

vi.mock('../models/workspace.sequelize', () => ({
  default: { findAll: mocks.findAll },
}));

vi.mock('./polarSubscriptionApply', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./polarSubscriptionApply')>();
  return {
    ...actual,
    persistPolarSubscriptionSnapshotOnWorkspace: mocks.persist,
  };
});

vi.mock('./metrics', () => ({
  observeIntegrationEvent: vi.fn(),
}));

import { observeIntegrationEvent } from './metrics';
import { reconcilePolarSubscriptionsFromApi } from './polarSubscriptionReconcile';

const log = {
  warn: vi.fn(),
  info: vi.fn(),
  error: vi.fn(),
} as import('fastify').FastifyBaseLogger;

function mockWorkspace(wsId: number, ownerId: number, polarSubId: string, billingPlan: string) {
  return {
    get: (k: string) => {
      if (k === 'id') return wsId;
      if (k === 'ownerUserId') return ownerId;
      if (k === 'polarSubscriptionId') return polarSubId;
      if (k === 'billingPlan') return billingPlan;
      return undefined;
    },
  };
}

beforeEach(() => {
  mocks.getSub.mockReset();
  mocks.findAll.mockReset();
  mocks.persist.mockReset();
  vi.mocked(observeIntegrationEvent).mockReset();
});

describe('reconcilePolarSubscriptionsFromApi', () => {
  it('dryRun reports drift when Polar active pro does not match DB free', async () => {
    mocks.findAll.mockResolvedValue([mockWorkspace(10, 1, 'sub_1', 'free')]);
    mocks.getSub.mockResolvedValue({
      id: 'sub_1',
      customerId: 'cus',
      productId: 'prod_pro',
      status: 'active',
      metadata: {},
    });

    const s = await reconcilePolarSubscriptionsFromApi({ log, limit: 50, dryRun: true });
    expect(s.scanned).toBe(1);
    expect(s.driftDetected).toBe(1);
    expect(s.rows[0]?.drift).toBe(true);
    expect(s.rows[0]?.updated).toBe(false);
    expect(s.rows[0]?.expectedPlan).toBe('cloud-pro');
    expect(mocks.persist).not.toHaveBeenCalled();
    expect(observeIntegrationEvent).toHaveBeenCalledWith('polar_reconcile_drift');
  });

  it('increments polarFetchErrors when Polar get throws', async () => {
    mocks.findAll.mockResolvedValue([mockWorkspace(11, 2, 'sub_x', 'free')]);
    mocks.getSub.mockRejectedValue(new Error('polar boom'));

    const s = await reconcilePolarSubscriptionsFromApi({ log, limit: 50, dryRun: true });
    expect(s.polarFetchErrors).toBe(1);
    expect(s.rows[0]?.error).toBe('polar boom');
    expect(observeIntegrationEvent).not.toHaveBeenCalled();
  });

  it('calls persist when not dryRun', async () => {
    mocks.findAll.mockResolvedValue([mockWorkspace(12, 3, 'sub_3', 'free')]);
    mocks.getSub.mockResolvedValue({
      id: 'sub_3',
      customerId: 'cus',
      productId: 'prod_pro',
      status: 'active',
      metadata: {},
    });
    mocks.persist.mockResolvedValue(true);

    const s = await reconcilePolarSubscriptionsFromApi({ log, limit: 50, dryRun: false });
    expect(mocks.persist).toHaveBeenCalledTimes(1);
    expect(s.rowsUpdated).toBe(1);
  });

  it('does not bump drift metric when DB already matches Polar', async () => {
    mocks.findAll.mockResolvedValue([mockWorkspace(13, 4, 'sub_4', 'cloud-pro')]);
    mocks.getSub.mockResolvedValue({
      id: 'sub_4',
      customerId: 'cus',
      productId: 'prod_pro',
      status: 'active',
      metadata: {},
    });

    await reconcilePolarSubscriptionsFromApi({ log, limit: 50, dryRun: true });
    expect(observeIntegrationEvent).not.toHaveBeenCalled();
  });
});
