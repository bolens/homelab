import type { Transaction } from 'sequelize';
import User from '../models/user.sequelize';
import Workspace from '../models/workspace.sequelize';

type UserRow = NonNullable<Awaited<ReturnType<typeof User.findByPk>>>;

/**
 * Ensures the user has a default workspace row (v1: exactly one per owner).
 * Copies current user billing/Polar mirror fields into the new workspace when creating.
 */
export async function ensureDefaultWorkspaceForUser(
  user: UserRow,
  options?: { transaction?: Transaction | null | undefined },
): Promise<number> {
  const existing = user.get('defaultWorkspaceId') as number | null | undefined;
  if (existing != null && Number(existing) > 0) {
    return Number(existing);
  }

  const ws = await Workspace.create(
    {
      ownerUserId: user.get('id') as number,
      billingPlan: (user.get('billingPlan') as string | null) ?? 'free',
      polarCustomerId: (user.get('polarCustomerId') as string | null) ?? null,
      polarSubscriptionId: (user.get('polarSubscriptionId') as string | null) ?? null,
    },
    { transaction: options?.transaction ?? null },
  );

  const wid = ws.get('id') as number;
  user.set('defaultWorkspaceId', wid);
  await user.save({ transaction: options?.transaction ?? null });
  return wid;
}

/** Resolves the workspace id to attach to a new poll for this creator (null for anonymous polls). */
export async function resolveWorkspaceIdForCreatorUserId(
  creatorUserId: number | null,
  options?: { transaction?: Transaction | null | undefined },
): Promise<number | null> {
  if (creatorUserId == null) return null;
  const user = await User.findByPk(creatorUserId, { transaction: options?.transaction ?? null });
  if (!user) return null;
  return ensureDefaultWorkspaceForUser(user, options);
}
