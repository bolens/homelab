import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  userFindByPk: vi.fn(),
  wsFindByPk: vi.fn(),
  wsFindOne: vi.fn(),
  ensure: vi.fn(),
}));

vi.mock('../models/user.sequelize', () => ({
  default: { findByPk: mocks.userFindByPk },
}));

vi.mock('../models/workspace.sequelize', () => ({
  default: { findByPk: mocks.wsFindByPk, findOne: mocks.wsFindOne },
}));

vi.mock('./workspaceBootstrap', () => ({
  ensureDefaultWorkspaceForUser: mocks.ensure,
}));

vi.mock('./env', () => ({
  appEnv: { polarProductIdCloudTeam: 'prod_team', polarProductIdCloudPro: 'prod_pro' },
}));

import type { Subscription } from '@polar-sh/sdk/models/components/subscription';
import { findWorkspaceForPolarSubscription } from './polarSubscriptionApply';

function sub(partial: Partial<Subscription>): Subscription {
  return {
    id: 'sub_99',
    customerId: 'cus_99',
    productId: 'prod_pro',
    status: 'active',
    metadata: {},
    ...partial,
  } as Subscription;
}

describe('findWorkspaceForPolarSubscription', () => {
  beforeEach(() => {
    mocks.userFindByPk.mockReset();
    mocks.wsFindByPk.mockReset();
    mocks.wsFindOne.mockReset();
    mocks.ensure.mockReset();
  });

  it('resolves by asking_ng_workspace_id before other strategies', async () => {
    const ws = { id: 9, get: (k: string) => (k === 'ownerUserId' ? 42 : undefined) };
    mocks.wsFindByPk.mockResolvedValue(ws);
    const got = await findWorkspaceForPolarSubscription(
      sub({ metadata: { asking_ng_workspace_id: '9' } }),
    );
    expect(got).toBe(ws);
    expect(mocks.wsFindByPk).toHaveBeenCalledWith(9);
    expect(mocks.userFindByPk).not.toHaveBeenCalled();
  });

  it('resolves by asking_ng_user_id after ensuring default workspace', async () => {
    const user = {
      get(k: string) {
        if (k === 'defaultWorkspaceId') return 5;
        return undefined;
      },
    };
    const ws = { id: 5 };
    mocks.userFindByPk.mockResolvedValue(user);
    mocks.ensure.mockResolvedValue(5);
    mocks.wsFindByPk.mockResolvedValue(ws);
    const got = await findWorkspaceForPolarSubscription(
      sub({ metadata: { asking_ng_user_id: '42' } }),
    );
    expect(got).toBe(ws);
    expect(mocks.userFindByPk).toHaveBeenCalledWith(42);
    expect(mocks.ensure).toHaveBeenCalledWith(user);
    expect(mocks.wsFindByPk).toHaveBeenCalledWith(5);
  });

  it('falls back to workspaces.polar_subscription_id', async () => {
    const ws = { id: 2 };
    mocks.wsFindOne.mockImplementation(async (q: { where?: Record<string, unknown> }) => {
      if (q?.where?.polarSubscriptionId === 'sub_99') return ws;
      return null;
    });
    const got = await findWorkspaceForPolarSubscription(sub({ metadata: {} }));
    expect(got).toBe(ws);
    expect(mocks.wsFindOne).toHaveBeenCalledWith({ where: { polarSubscriptionId: 'sub_99' } });
  });

  it('rejects workspace metadata when owner mismatches asking_ng_user_id and falls back to user default workspace', async () => {
    const wsWrongOwner = { id: 9, get: (k: string) => (k === 'ownerUserId' ? 999 : undefined) };
    const user = {
      get(k: string) {
        if (k === 'defaultWorkspaceId') return 5;
        return undefined;
      },
    };
    const wsDefault = { id: 5, get: (k: string) => (k === 'ownerUserId' ? 42 : undefined) };
    mocks.wsFindByPk.mockImplementation(async (id: number) => {
      if (id === 9) return wsWrongOwner;
      if (id === 5) return wsDefault;
      return null;
    });
    mocks.userFindByPk.mockResolvedValue(user);
    mocks.ensure.mockResolvedValue(5);
    const got = await findWorkspaceForPolarSubscription(
      sub({ metadata: { asking_ng_workspace_id: '9', asking_ng_user_id: '42' } }),
    );
    expect(got).toBe(wsDefault);
  });

  it('scopes subscription/customer fallback lookups by asking_ng_user_id owner when provided', async () => {
    const ws = { id: 13 };
    mocks.userFindByPk.mockResolvedValue(null);
    mocks.wsFindOne.mockImplementation(async (q: { where?: Record<string, unknown> }) => {
      if (q?.where?.polarSubscriptionId === 'sub_99' && q?.where?.ownerUserId === 42) return ws;
      return null;
    });
    const got = await findWorkspaceForPolarSubscription(
      sub({ metadata: { asking_ng_user_id: '42' } }),
    );
    expect(got).toBe(ws);
    expect(mocks.wsFindOne).toHaveBeenCalledWith({
      where: { polarSubscriptionId: 'sub_99', ownerUserId: 42 },
    });
  });

  it('falls back to workspaces.polar_customer_id when subscription id unmatched', async () => {
    const ws = { id: 3 };
    mocks.wsFindOne.mockImplementation(async (q: { where?: Record<string, unknown> }) => {
      if (q?.where?.polarSubscriptionId === 'sub_99') return null;
      if (q?.where?.polarCustomerId === 'cus_99') return ws;
      return null;
    });
    const got = await findWorkspaceForPolarSubscription(sub({}));
    expect(got).toBe(ws);
    expect(mocks.wsFindOne).toHaveBeenCalledTimes(2);
  });

  it('ignores non-positive asking_ng_user_id and uses polar_subscription_id', async () => {
    const ws = { id: 10 };
    mocks.wsFindOne.mockImplementation(async (q: { where?: Record<string, unknown> }) => {
      if (q?.where?.polarSubscriptionId === 'sub_99') return ws;
      return null;
    });
    const got = await findWorkspaceForPolarSubscription(
      sub({ metadata: { asking_ng_user_id: '0' } }),
    );
    expect(got).toBe(ws);
    expect(mocks.userFindByPk).not.toHaveBeenCalled();
  });

  it('falls back when asking_ng_user_id is valid but user row missing', async () => {
    const ws = { id: 11 };
    mocks.userFindByPk.mockResolvedValue(null);
    mocks.wsFindOne.mockImplementation(async (q: { where?: Record<string, unknown> }) => {
      if (q?.where?.polarSubscriptionId === 'sub_99') return ws;
      return null;
    });
    const got = await findWorkspaceForPolarSubscription(
      sub({ metadata: { asking_ng_user_id: '7' } }),
    );
    expect(got).toBe(ws);
    expect(mocks.userFindByPk).toHaveBeenCalledWith(7);
    expect(mocks.wsFindOne).toHaveBeenCalledTimes(1);
  });

  it('returns null when nothing matches', async () => {
    mocks.userFindByPk.mockResolvedValue(null);
    mocks.wsFindOne.mockResolvedValue(null);
    const got = await findWorkspaceForPolarSubscription(sub({}));
    expect(got).toBeNull();
    expect(mocks.wsFindOne).toHaveBeenCalledTimes(2);
  });
});
