import { describe, expect, it } from 'vitest';
import { billingUsageWarningSeverity } from './profileBillingApi';

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
