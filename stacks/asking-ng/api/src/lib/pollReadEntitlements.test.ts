import { afterEach, describe, expect, it, vi } from 'vitest';

const { mockFields, mockLicenseExpired } = vi.hoisted(() => ({
  mockFields: vi.fn(),
  mockLicenseExpired: vi.fn(),
}));

vi.mock('../controller/self/self.repository', () => ({
  findBillingPlanAndRoleForVoteQuota: (args: { creatorUserId: number }) =>
    mockFields(args.creatorUserId),
}));

vi.mock('./billingLimits', () => ({
  hasForensicReplayForBillingPlan: (plan: string) => plan !== 'free',
  hasVoteHeatmapForBillingPlan: (plan: string) => plan !== 'free',
}));

vi.mock('./selfhostProLicense', () => ({
  selfhostProLicenseExpiredDetailsForPlan: (plan: string) => mockLicenseExpired(plan),
}));

vi.mock('./env', () => ({
  appEnv: { billingEnforceLimits: true },
}));

describe('checkPollReadEntitlements', () => {
  afterEach(() => {
    vi.resetModules();
    mockFields.mockReset();
    mockLicenseExpired.mockReset();
  });

  it('returns forensic plan limit for free plan', async () => {
    mockFields.mockResolvedValue({ billingPlan: 'free', role: 'user' });
    mockLicenseExpired.mockReturnValue(null);
    const { checkPollReadEntitlements } = await import('./pollReadEntitlements');
    await expect(
      checkPollReadEntitlements({
        pollId: 'p1',
        ownerUserId: 1,
        feature: 'forensic_replay',
      }),
    ).resolves.toEqual({
      kind: 'plan_limit_forensic',
      plan: 'free',
      requiredPlan: 'cloud-team',
    });
  });

  it('returns heatmap plan limit for free plan', async () => {
    mockFields.mockResolvedValue({ billingPlan: 'free', role: 'user' });
    mockLicenseExpired.mockReturnValue(null);
    const { checkPollReadEntitlements } = await import('./pollReadEntitlements');
    await expect(
      checkPollReadEntitlements({
        pollId: 'p1',
        ownerUserId: 1,
        feature: 'vote_heatmap',
      }),
    ).resolves.toEqual({
      kind: 'plan_limit_heatmap',
      plan: 'free',
      requiredPlan: 'cloud-team',
    });
  });

  it('allows superadmin on free plan read features', async () => {
    mockFields.mockResolvedValue({ billingPlan: 'free', role: 'superadmin' });
    mockLicenseExpired.mockReturnValue(null);
    const { checkPollReadEntitlements } = await import('./pollReadEntitlements');
    await expect(
      checkPollReadEntitlements({
        pollId: 'p1',
        ownerUserId: 1,
        feature: 'forensic_replay',
      }),
    ).resolves.toBeNull();
  });
});
