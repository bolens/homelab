import { afterEach, describe, expect, it, vi } from 'vitest';

const { mockCountVotes, mockFields } = vi.hoisted(() => ({
  mockCountVotes: vi.fn(),
  mockFields: vi.fn(),
}));

vi.mock('../controller/self/self.repository', () => ({
  findBillingPlanAndRoleForVoteQuota: (args: { creatorUserId: number }) => mockFields(args.creatorUserId),
}));

vi.mock('../controller/poll/voteOnPoll.repository', () => ({
  countBillableVotesForCreatorUtcMonth: (args: { creatorUserId: number }) => mockCountVotes(args.creatorUserId),
}));

vi.mock('./env', () => ({
  appEnv: { billingEnforceLimits: true },
}));

describe('billingVoteQuota', () => {
  afterEach(() => {
    vi.resetModules();
    mockCountVotes.mockReset();
    mockFields.mockReset();
  });

  it('allows when under cap', async () => {
    mockFields.mockResolvedValue({ billingPlan: 'free', role: 'user' });
    mockCountVotes.mockResolvedValue(49_999);
    const { checkMonthlyVoteQuotaForCreator } = await import('./billingVoteQuota');
    await expect(
      checkMonthlyVoteQuotaForCreator({ creatorUserId: 1, incomingVoteRows: 1 }),
    ).resolves.toEqual({ ok: true });
  });

  it('denies when incoming would exceed cap', async () => {
    mockFields.mockResolvedValue({ billingPlan: 'free', role: 'user' });
    mockCountVotes.mockResolvedValue(50_000);
    const { checkMonthlyVoteQuotaForCreator } = await import('./billingVoteQuota');
    await expect(
      checkMonthlyVoteQuotaForCreator({ creatorUserId: 1, incomingVoteRows: 1 }),
    ).resolves.toEqual({
      ok: false,
      max: 50_000,
      current: 50_000,
      plan: 'free',
      incoming: 1,
    });
  });

  it('skips for superadmin creator', async () => {
    mockFields.mockResolvedValue({ billingPlan: 'free', role: 'superadmin' });
    const { checkMonthlyVoteQuotaForCreator } = await import('./billingVoteQuota');
    await expect(
      checkMonthlyVoteQuotaForCreator({ creatorUserId: 1, incomingVoteRows: 5 }),
    ).resolves.toEqual({ ok: true });
    expect(mockCountVotes).not.toHaveBeenCalled();
  });

  it('skips count for unlimited plan', async () => {
    mockFields.mockResolvedValue({ billingPlan: 'selfhost-pro', role: 'user' });
    const { checkMonthlyVoteQuotaForCreator } = await import('./billingVoteQuota');
    await expect(
      checkMonthlyVoteQuotaForCreator({ creatorUserId: 1, incomingVoteRows: 1_000_000 }),
    ).resolves.toEqual({ ok: true });
    expect(mockCountVotes).not.toHaveBeenCalled();
  });
});
