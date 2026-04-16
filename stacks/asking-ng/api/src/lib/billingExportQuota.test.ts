import { afterEach, describe, expect, it, vi } from 'vitest';

const { mockQuery, mockFind } = vi.hoisted(() => ({
  mockQuery: vi.fn(),
  mockFind: vi.fn(),
}));

vi.mock('../connections', () => ({
  default: {
    query: (...args: unknown[]) => mockQuery(...args),
    define: vi.fn(() => ({})),
  },
}));

vi.mock('../controller/self/self.repository', () => ({
  findBillingPlanAndRoleByUserId: (id: number) => mockFind(id),
}));

vi.mock('./env', () => ({
  appEnv: { billingEnforceLimits: true },
}));

describe('billingExportQuota checkDailyDataExportQuotaForWorkspace', () => {
  afterEach(() => {
    vi.resetModules();
    mockQuery.mockReset();
    mockFind.mockReset();
  });

  it('allows when under daily cap', async () => {
    mockFind.mockResolvedValue({ billingPlan: 'free', role: 'user' });
    mockQuery.mockResolvedValue([{ c: 2 }]);
    const { checkDailyDataExportQuotaForWorkspace } = await import('./billingExportQuota');
    await expect(checkDailyDataExportQuotaForWorkspace({ workspaceUserId: 1 })).resolves.toEqual({ ok: true });
  });

  it('denies when at daily cap', async () => {
    mockFind.mockResolvedValue({ billingPlan: 'free', role: 'user' });
    mockQuery.mockResolvedValue([{ c: 3 }]);
    const { checkDailyDataExportQuotaForWorkspace } = await import('./billingExportQuota');
    await expect(checkDailyDataExportQuotaForWorkspace({ workspaceUserId: 1 })).resolves.toEqual({
      ok: false,
      max: 3,
      current: 3,
      plan: 'free',
    });
  });

  it('skips for superadmin', async () => {
    mockFind.mockResolvedValue({ billingPlan: 'free', role: 'superadmin' });
    const { checkDailyDataExportQuotaForWorkspace } = await import('./billingExportQuota');
    await expect(checkDailyDataExportQuotaForWorkspace({ workspaceUserId: 1 })).resolves.toEqual({ ok: true });
    expect(mockQuery).not.toHaveBeenCalled();
  });
});
