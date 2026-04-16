import { afterEach, describe, expect, it, vi } from 'vitest';

const { mockFields } = vi.hoisted(() => ({
  mockFields: vi.fn(),
}));

vi.mock('../controller/self/self.repository', () => ({
  findBillingPlanAndRoleByUserId: (id: number) => mockFields(id),
}));

const envMutable = vi.hoisted(() => ({
  billingEnforceLimits: false,
  wsMaxSubscribersPerPoll: 250,
}));

vi.mock('./env', () => ({
  get appEnv() {
    return envMutable;
  },
}));

describe('billingWsQuota', () => {
  afterEach(() => {
    vi.resetModules();
    mockFields.mockReset();
    envMutable.billingEnforceLimits = false;
    envMutable.wsMaxSubscribersPerPoll = 250;
  });

  it('returns env cap when billing limits are off', async () => {
    envMutable.billingEnforceLimits = false;
    envMutable.wsMaxSubscribersPerPoll = 400;
    const { resolveEffectivePollLiveRoomCap } = await import('./billingWsQuota');
    await expect(resolveEffectivePollLiveRoomCap(99)).resolves.toBe(400);
    expect(mockFields).not.toHaveBeenCalled();
  });

  it('returns min(env, free tier) for orphan polls when billing limits are on', async () => {
    envMutable.billingEnforceLimits = true;
    envMutable.wsMaxSubscribersPerPoll = 500;
    const { resolveEffectivePollLiveRoomCap } = await import('./billingWsQuota');
    await expect(resolveEffectivePollLiveRoomCap(null)).resolves.toBe(100);
    expect(mockFields).not.toHaveBeenCalled();
  });

  it('returns min(env, plan tier) for normal owners', async () => {
    envMutable.billingEnforceLimits = true;
    envMutable.wsMaxSubscribersPerPoll = 500;
    mockFields.mockResolvedValue({ billingPlan: 'free', role: 'user' });
    const { resolveEffectivePollLiveRoomCap } = await import('./billingWsQuota');
    await expect(resolveEffectivePollLiveRoomCap(7)).resolves.toBe(100);
  });

  it('returns env cap for superadmin owners', async () => {
    envMutable.billingEnforceLimits = true;
    envMutable.wsMaxSubscribersPerPoll = 320;
    mockFields.mockResolvedValue({ billingPlan: 'free', role: 'superadmin' });
    const { resolveEffectivePollLiveRoomCap } = await import('./billingWsQuota');
    await expect(resolveEffectivePollLiveRoomCap(1)).resolves.toBe(320);
  });

  it('returns env cap when plan tier is unlimited', async () => {
    envMutable.billingEnforceLimits = true;
    envMutable.wsMaxSubscribersPerPoll = 900;
    mockFields.mockResolvedValue({ billingPlan: 'selfhost-pro', role: 'user' });
    const { resolveEffectivePollLiveRoomCap } = await import('./billingWsQuota');
    await expect(resolveEffectivePollLiveRoomCap(2)).resolves.toBe(900);
  });
});
