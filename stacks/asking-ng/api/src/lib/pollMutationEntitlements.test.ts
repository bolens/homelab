import { afterEach, describe, expect, it, vi } from 'vitest';

const { mockFields, mockLicenseExpired } = vi.hoisted(() => ({
  mockFields: vi.fn(),
  mockLicenseExpired: vi.fn(),
}));

vi.mock('../controller/self/self.repository', () => ({
  findBillingPlanAndRoleByUserId: (userId: number) => mockFields(userId),
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

describe('checkPollMutationEntitlements', () => {
  afterEach(() => {
    vi.resetModules();
    mockFields.mockReset();
    mockLicenseExpired.mockReset();
  });

  it('returns automation plan limit for free plan', async () => {
    mockFields.mockResolvedValue({ billingPlan: 'free', role: 'user' });
    mockLicenseExpired.mockReturnValue(null);
    const { checkPollMutationEntitlements } = await import('./pollMutationEntitlements');
    await expect(
      checkPollMutationEntitlements({
        ownerUserId: 42,
        requiresAutomation: true,
        requiresRetention: false,
      }),
    ).resolves.toEqual({
      kind: 'plan_limit_automation',
      plan: 'free',
      requiredPlan: 'cloud-team',
    });
  });

  it('returns license-expired before plan limits', async () => {
    mockFields.mockResolvedValue({ billingPlan: 'selfhost-pro', role: 'user' });
    mockLicenseExpired.mockReturnValue({
      plan: 'selfhost-pro',
      license_status: 'expired',
      license_valid_until_ms: 1,
      license_last_verified_ms: 2,
      license_grace_until_ms: 3,
      upgrade_hint: 'renew',
    });
    const { checkPollMutationEntitlements } = await import('./pollMutationEntitlements');
    await expect(
      checkPollMutationEntitlements({
        ownerUserId: 42,
        requiresAutomation: true,
        requiresRetention: true,
      }),
    ).resolves.toMatchObject({ kind: 'billing_license_expired' });
  });

  it('allows superadmin even on free plan requirements', async () => {
    mockFields.mockResolvedValue({ billingPlan: 'free', role: 'superadmin' });
    mockLicenseExpired.mockReturnValue(null);
    const { checkPollMutationEntitlements } = await import('./pollMutationEntitlements');
    await expect(
      checkPollMutationEntitlements({
        ownerUserId: 42,
        requiresAutomation: true,
        requiresRetention: true,
      }),
    ).resolves.toBeNull();
  });
});
