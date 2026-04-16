import { afterEach, describe, expect, it, vi } from 'vitest';

const { mockCount, mockPlan } = vi.hoisted(() => ({
  mockCount: vi.fn(),
  mockPlan: vi.fn(),
}));

vi.mock('../controller/self/self.repository', () => ({
  countNonArchivedPollsOwnedByUser: (id: number) => mockCount(id),
  findBillingPlanByUserId: (id: number) => mockPlan(id),
}));

vi.mock('./env', () => ({
  appEnv: { billingEnforceLimits: true },
}));

describe('billingPollQuota', () => {
  afterEach(() => {
    vi.resetModules();
    mockCount.mockReset();
    mockPlan.mockReset();
  });

  it('allows when under cap', async () => {
    mockPlan.mockResolvedValue('free');
    mockCount.mockResolvedValue(19);
    const { checkActivePollQuotaForUser } = await import('./billingPollQuota');
    await expect(
      checkActivePollQuotaForUser({ creatorUserId: 1, sessionUserRole: 'user' }),
    ).resolves.toEqual({ ok: true });
  });

  it('denies at cap', async () => {
    mockPlan.mockResolvedValue('free');
    mockCount.mockResolvedValue(20);
    const { checkActivePollQuotaForUser } = await import('./billingPollQuota');
    await expect(
      checkActivePollQuotaForUser({ creatorUserId: 1, sessionUserRole: 'user' }),
    ).resolves.toEqual({
      ok: false,
      max: 20,
      current: 20,
      plan: 'free',
    });
  });

  it('skips for superadmin', async () => {
    mockCount.mockResolvedValue(9999);
    const { checkActivePollQuotaForUser } = await import('./billingPollQuota');
    await expect(
      checkActivePollQuotaForUser({ creatorUserId: 1, sessionUserRole: 'superadmin' }),
    ).resolves.toEqual({ ok: true });
    expect(mockCount).not.toHaveBeenCalled();
  });
});
