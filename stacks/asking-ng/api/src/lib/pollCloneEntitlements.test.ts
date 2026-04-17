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
  hasWebhookAutomationForBillingPlan: (plan: string) => plan !== 'free',
  hasExtendedRetentionForBillingPlan: (plan: string) => plan !== 'free',
}));

vi.mock('./selfhostProLicense', () => ({
  selfhostProLicenseExpiredDetailsForPlan: (plan: string) => mockLicenseExpired(plan),
}));

vi.mock('./env', () => ({
  appEnv: { billingEnforceLimits: true },
}));

describe('pollCloneEntitlements', () => {
  afterEach(() => {
    vi.resetModules();
    mockFields.mockReset();
    mockLicenseExpired.mockReset();
  });

  it('normalizes clone premium fields from source poll', async () => {
    const { normalizeClonePremiumFields } = await import('./pollCloneEntitlements');
    const source = {
      get(key: string) {
        if (key === 'webhookTargets')
          return [
            {
              url: ' https://x.test/h ',
              secret: ' secret ',
              hint_locale: 'ES',
              include_results_snapshot: true,
              include_owner_snapshot: true,
              include_owner_events: true,
            },
            { url: '', secret: 's' },
          ];
        if (key === 'retentionTtlDays') return 30;
        if (key === 'retentionLegalHold') return true;
        return null;
      },
    };
    expect(normalizeClonePremiumFields(source)).toEqual({
      webhookTargets: [
        {
          url: 'https://x.test/h',
          secret: 'secret',
          hint_locale: 'es',
          include_results_snapshot: true,
          include_owner_snapshot: true,
          include_owner_events: true,
        },
      ],
      retentionTtlDays: 30,
      retentionLegalHold: true,
    });
  });

  it('returns retention plan limit for free plan source retention fields', async () => {
    mockFields.mockResolvedValue({ billingPlan: 'free', role: 'user' });
    mockLicenseExpired.mockReturnValue(null);
    const { checkClonePremiumEntitlements } = await import('./pollCloneEntitlements');
    const source = {
      get(key: string) {
        if (key === 'webhookTargets') return [];
        if (key === 'retentionTtlDays') return 7;
        if (key === 'retentionLegalHold') return false;
        return null;
      },
    };
    await expect(
      checkClonePremiumEntitlements({
        pollId: 'p1',
        ownerId: 1,
        source,
      }),
    ).resolves.toEqual({
      kind: 'plan_limit_retention',
      plan: 'free',
      requiredPlan: 'cloud-team',
    });
  });

  it('returns null when no premium clone fields are present', async () => {
    const { checkClonePremiumEntitlements } = await import('./pollCloneEntitlements');
    const source = {
      get(key: string) {
        if (key === 'webhookTargets') return [];
        if (key === 'retentionTtlDays') return null;
        if (key === 'retentionLegalHold') return false;
        return null;
      },
    };
    await expect(
      checkClonePremiumEntitlements({
        pollId: 'p1',
        ownerId: 1,
        source,
      }),
    ).resolves.toBeNull();
  });
});
