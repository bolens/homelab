import User from '../../models/user.sequelize';
import Workspace from '../../models/workspace.sequelize';
import { Op, type Transaction } from 'sequelize';
import Poll from '../../model/Poll';
import Vote from '../../model/Vote';

export async function findUserById(id: number) {
  return User.findByPk(id);
}

export async function findProfileById(id: number) {
  return User.findByPk(id, {
    attributes: ['id', 'homelab-user', 'role', 'llmGatewayToken', 'billingPlan'],
  });
}

export async function findBillingPlanByUserId(userId: number): Promise<string> {
  const row = await User.findByPk(userId, { attributes: ['defaultWorkspaceId', 'billingPlan'] });
  if (!row) return 'free';
  const wsId = row.get('defaultWorkspaceId') as number | null | undefined;
  if (wsId != null && wsId > 0) {
    const ws = await Workspace.findByPk(wsId, { attributes: ['billingPlan'] });
    if (ws) return (ws.get('billingPlan') as string | null) ?? 'free';
  }
  return (row.get('billingPlan') as string | null) ?? 'free';
}

export async function findBillingPlanAndRoleByUserId(
  userId: number,
): Promise<{ billingPlan: string; role: string | null }> {
  const row = await User.findByPk(userId, { attributes: ['defaultWorkspaceId', 'billingPlan', 'role'] });
  if (!row) {
    return { billingPlan: 'free', role: null };
  }
  let billingPlan = (row.get('billingPlan') as string | null) ?? 'free';
  const wsId = row.get('defaultWorkspaceId') as number | null | undefined;
  if (wsId != null && wsId > 0) {
    const ws = await Workspace.findByPk(wsId, { attributes: ['billingPlan'] });
    if (ws) billingPlan = (ws.get('billingPlan') as string | null) ?? 'free';
  }
  return {
    billingPlan,
    role: (row.get('role') as string | null) ?? null,
  };
}

/** Billing plan for vote/export limits: `polls.workspace_id` when set, else creator’s default workspace / user mirror. */
export async function findBillingPlanAndRoleForVoteQuota(args: {
  pollId: string | null | undefined;
  creatorUserId: number;
}): Promise<{ billingPlan: string; role: string | null }> {
  const raw = args.pollId?.trim();
  if (raw) {
    const poll = await Poll.findByPk(raw, { attributes: ['workspaceId'] });
    const wsId = poll?.get('workspaceId') as number | null | undefined;
    if (wsId != null && wsId > 0) {
      const [ws, userRow] = await Promise.all([
        Workspace.findByPk(wsId, { attributes: ['billingPlan'] }),
        User.findByPk(args.creatorUserId, { attributes: ['role'] }),
      ]);
      if (ws) {
        return {
          billingPlan: (ws.get('billingPlan') as string | null) ?? 'free',
          role: (userRow?.get('role') as string | null) ?? null,
        };
      }
    }
  }
  return findBillingPlanAndRoleByUserId(args.creatorUserId);
}

export async function countNonArchivedPollsOwnedByUser(userId: number): Promise<number> {
  return Poll.count({ where: { creatorUserId: userId, archived: false } });
}

export async function findPollsOwnedByUser(userId: number) {
  return Poll.findAll({ where: { creatorUserId: userId }, order: [['id', 'ASC']] });
}

export async function findPollsSharedWithUser(userId: number) {
  return Poll.findAll({
    where: { sharedEditorUserIds: { [Op.contains]: [userId] } },
    attributes: ['id', 'title', 'phase', 'creatorUserId', 'sharedEditorUserIds'],
    order: [['id', 'ASC']],
  });
}

export async function findVotesForUser(userId: number) {
  return Vote.findAll({
    where: { userId: userId },
    order: [['id', 'DESC']],
    limit: 100_000,
  });
}

export async function anonymizeUserReferences(id: number, transaction: Transaction) {
  await Poll.update(
    { creatorUserId: null },
    { where: { creatorUserId: id }, transaction },
  );

  const polls = await Poll.findAll({
    attributes: ['id', 'sharedEditorUserIds'],
    where: { sharedEditorUserIds: { [Op.contains]: [id] } },
    transaction,
  });
  for (const poll of polls) {
    const raw = poll.get('sharedEditorUserIds');
    if (!Array.isArray(raw)) continue;
    const next = raw.filter((v) => Number(v) !== id);
    if (next.length === raw.length) continue;
    poll.set('sharedEditorUserIds', next);
    await poll.save({ transaction });
  }

  await Vote.update({ userId: null }, { where: { userId: id }, transaction });
  await Vote.update({ quarantineDecidedBy: null }, { where: { quarantineDecidedBy: id }, transaction });
}
