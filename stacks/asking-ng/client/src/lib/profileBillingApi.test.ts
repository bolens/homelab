import { describe, expect, it } from 'vitest';
import {
  billingExportReminder,
  billingPastDueBannerPayload,
  billingUpgradeHintFromError,
  billingUpgradeUrlForRequiredPlan,
  billingUsageWarningSeverity,
} from './profileBillingApi';

describe('billingUsageWarningSeverity', () => {
  it('returns null when limits are not enforced', () => {
    expect(
      billingUsageWarningSeverity({
        usage: { limitsEnforced: false, warnings: { activePolls: '95' } },
      }),
    ).toBeNull();
  });

  it('returns null when warnings are absent', () => {
    expect(
      billingUsageWarningSeverity({
        usage: { limitsEnforced: true },
      }),
    ).toBeNull();
  });

  it('prefers 95 over 80 across dimensions', () => {
    expect(
      billingUsageWarningSeverity({
        usage: {
          limitsEnforced: true,
          warnings: { activePolls: '80', votesThisMonth: '95', dataExports: '80' },
        },
      }),
    ).toBe('95');
  });

  it('returns 80 when no dimension is at 95', () => {
    expect(
      billingUsageWarningSeverity({
        usage: {
          limitsEnforced: true,
          warnings: { dataExports: '80' },
        },
      }),
    ).toBe('80');
  });
});

describe('billingUpgradeHintFromError', () => {
  it('returns renewal hint for BILLING_LICENSE_EXPIRED', () => {
    const e = Object.assign(new Error('expired'), {
      status: 403,
      errorCode: 'BILLING_LICENSE_EXPIRED',
      details: { upgrade_hint: 'renew', required_plan: 'cloud-team' },
    });
    const hint = billingUpgradeHintFromError(e, {
      polar: { customerPortalUrl: 'https://portal.test' },
    });
    expect(hint.isLicenseRenewal).toBe(true);
    expect(hint.url).toBe('https://portal.test');
  });

  it('returns upgrade hint for PLAN_LIMIT', () => {
    const e = Object.assign(new Error('plan'), {
      status: 403,
      errorCode: 'PLAN_LIMIT_AUTOMATION',
      details: { required_plan: 'cloud-pro' },
    });
    const hint = billingUpgradeHintFromError(e, {
      polar: {
        checkoutCloudTeamUrl: 'https://team.test',
        checkoutCloudProUrl: 'https://pro.test',
      },
    });
    expect(hint.isLicenseRenewal).toBe(false);
    expect(hint.url).toBe('https://pro.test');
  });

  it('returns upgrade hint for USAGE_LIMIT from free to cloud-team', () => {
    const e = Object.assign(new Error('usage'), {
      status: 403,
      errorCode: 'USAGE_LIMIT_EXPORTS',
      details: { current: 3, max: 3, plan: 'free' },
    });
    const hint = billingUpgradeHintFromError(e, {
      billing: { plan: 'free' },
      polar: {
        checkoutCloudTeamUrl: 'https://team.test',
        checkoutCloudProUrl: 'https://pro.test',
      },
    });
    expect(hint.isLicenseRenewal).toBe(false);
    expect(hint.url).toBe('https://team.test');
  });

  it('returns upgrade hint for USAGE_LIMIT from cloud-team to cloud-pro', () => {
    const e = Object.assign(new Error('usage'), {
      status: 403,
      errorCode: 'USAGE_LIMIT_VOTES',
      details: { current: 1_000_000, max: 1_000_000, plan: 'cloud-team' },
    });
    const hint = billingUpgradeHintFromError(e, {
      billing: { plan: 'cloud-team' },
      polar: {
        checkoutCloudTeamUrl: 'https://team.test',
        checkoutCloudProUrl: 'https://pro.test',
      },
    });
    expect(hint.isLicenseRenewal).toBe(false);
    expect(hint.url).toBe('https://pro.test');
  });
});

describe('billingUpgradeUrlForRequiredPlan', () => {
  const data = {
    polar: {
      customerPortalUrl: 'https://portal.test',
      checkoutCloudTeamUrl: 'https://team.test',
      checkoutCloudProUrl: 'https://pro.test',
    },
  };

  it('prefers cloud-pro checkout for required cloud-pro', () => {
    expect(billingUpgradeUrlForRequiredPlan(data, 'cloud-pro')).toBe('https://pro.test');
  });

  it('uses cloud-team checkout for required cloud-team', () => {
    expect(billingUpgradeUrlForRequiredPlan(data, 'cloud-team')).toBe('https://team.test');
  });

  it('falls back to portal when required plan is unknown', () => {
    expect(billingUpgradeUrlForRequiredPlan(data, 'enterprise-custom')).toBe('https://portal.test');
  });

  it('returns null when no URLs are configured', () => {
    expect(billingUpgradeUrlForRequiredPlan({}, 'cloud-team')).toBeNull();
  });
});

describe('billingExportReminder', () => {
  it('returns null when limits are disabled', () => {
    expect(billingExportReminder({ usage: { limitsEnforced: false } })).toBeNull();
  });

  it('returns reminder payload and near-cap status', () => {
    expect(
      billingExportReminder({
        usage: {
          limitsEnforced: true,
          exportsToday: 19,
          maxExportsPerDay: 20,
          warnings: { dataExports: '95' },
        },
      }),
    ).toEqual({
      current: 19,
      max: 20,
      remaining: 1,
      atCap: false,
      nearCap: '95',
    });
  });
});

describe('billingPastDueBannerPayload', () => {
  it('returns null when billing is not past due', () => {
    expect(
      billingPastDueBannerPayload({
        billing: { pastDue: false },
        polar: { customerPortalUrl: 'https://portal.test' },
      }),
    ).toBeNull();
  });

  it('returns null when portal URL is missing', () => {
    expect(
      billingPastDueBannerPayload({
        billing: { pastDue: true },
        polar: { customerPortalUrl: '   ' },
      }),
    ).toBeNull();
  });

  it('returns trimmed portal URL when past due', () => {
    expect(
      billingPastDueBannerPayload({
        billing: { pastDue: true },
        polar: { customerPortalUrl: ' https://portal.test ' },
      }),
    ).toEqual({ portalUrl: 'https://portal.test' });
  });
});
