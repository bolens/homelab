import type { ProfileUpdateBody } from '../../schemas/profile';
import type { SelfDeleteBody, SelfPasswordChangeBody } from '../../schemas/userSelf';
import { comparePassword, hashPassword } from '../../utils/auth';
import sequelize from '../../connections';
import {
  anonymizeUserReferences,
  findBillingPlanByUserId,
  findPollsOwnedByUser,
  findPollsSharedWithUser,
  findProfileById,
  findUserById,
  findVotesForUser,
} from './self.repository';

type ProfileSummary = {
  id: number;
  homelab-user: string;
  role: string;
  llmGatewayToken: string | null;
  billingPlan: string;
};

function toProfileSummary(
  user: { get(key: 'id' | 'homelab-user' | 'role' | 'llmGatewayToken' | 'billingPlan'): unknown },
  billingPlanOverride?: string,
) {
  return {
    id: user.get('id') as number,
    homelab-user: user.get('homelab-user') as string,
    role: user.get('role') as string,
    llmGatewayToken: (user.get('llmGatewayToken') as string | null) ?? null,
    billingPlan: billingPlanOverride ?? ((user.get('billingPlan') as string | null) ?? 'free'),
  } satisfies ProfileSummary;
}

export type GetProfileResult = { kind: 'not_found' } | { kind: 'ok'; user: ProfileSummary };

export async function getProfileService(args: { userId: number | null }): Promise<GetProfileResult> {
  if (args.userId == null) return { kind: 'not_found' };
  const user = await findProfileById(args.userId);
  if (!user) return { kind: 'not_found' };
  const billingPlan = await findBillingPlanByUserId(args.userId);
  return { kind: 'ok', user: toProfileSummary(user, billingPlan) };
}

export type UpdateProfileResult = { kind: 'not_found' } | { kind: 'ok'; user: ProfileSummary };

export async function updateProfileService(args: {
  userId: number | null;
  body: ProfileUpdateBody;
}): Promise<UpdateProfileResult> {
  if (args.userId == null) return { kind: 'not_found' };
  const user = await findUserById(args.userId);
  if (!user) return { kind: 'not_found' };

  const { homelab-user, password } = args.body;
  if (homelab-user) user.set('homelab-user', homelab-user);
  if (password) user.set('password', hashPassword(password));
  if (Object.prototype.hasOwnProperty.call(args.body as object, 'llmGatewayToken')) {
    user.set('llmGatewayToken', args.body.llmGatewayToken);
  }
  await user.save();
  const billingPlan = await findBillingPlanByUserId(args.userId);
  return { kind: 'ok', user: toProfileSummary(user, billingPlan) };
}

export type UpdateSelfPasswordResult =
  | { kind: 'not_found' }
  | { kind: 'invalid_credentials' }
  | { kind: 'ok' };

export async function updateSelfPasswordService(args: {
  userId: number | null;
  body: SelfPasswordChangeBody;
}): Promise<UpdateSelfPasswordResult> {
  if (args.userId == null) return { kind: 'not_found' };
  const user = await findUserById(args.userId);
  if (!user || !comparePassword(args.body.oldPassword, user.get('password') as string)) {
    return { kind: 'invalid_credentials' };
  }
  user.set('password', hashPassword(args.body.newPassword));
  await user.save();
  return { kind: 'ok' };
}

export type DeleteSelfResult = { kind: 'not_found' } | { kind: 'invalid_credentials' } | { kind: 'ok' };

export type ExportSelfDataResult = { kind: 'not_found' } | { kind: 'ok'; payload: Record<string, unknown> };

/** Portable account + poll + vote export for the signed-in user (password never included). */
export async function exportSelfDataService(args: { userId: number | null }): Promise<ExportSelfDataResult> {
  if (args.userId == null) return { kind: 'not_found' };
  const user = await findUserById(args.userId);
  if (!user) return { kind: 'not_found' };

  const account = user.get({ plain: true }) as Record<string, unknown>;
  delete account.password;
  delete account.llmGatewayToken;
  account.has_llm_gateway_token = Boolean(user.get('llmGatewayToken'));

  const ownedPolls = await findPollsOwnedByUser(args.userId);
  const sharedPolls = await findPollsSharedWithUser(args.userId);
  const votes = await findVotesForUser(args.userId);

  const payload = {
    exported_at: new Date().toISOString(),
    export_version: 1,
    account,
    polls_owned: ownedPolls.map((p) => p.get({ plain: true })),
    polls_shared_drafts: sharedPolls.map((p) => p.get({ plain: true })),
    votes: votes.map((v) => v.get({ plain: true })),
  };

  return { kind: 'ok', payload };
}

export async function deleteSelfService(args: {
  userId: number | null;
  body: SelfDeleteBody;
}): Promise<DeleteSelfResult> {
  if (args.userId == null) return { kind: 'not_found' };
  const user = await findUserById(args.userId);
  if (!user || !comparePassword(args.body.password, user.get('password') as string)) {
    return { kind: 'invalid_credentials' };
  }

  await sequelize.transaction(async (transaction) => {
    await anonymizeUserReferences(args.userId as number, transaction);
    await user.destroy({ transaction });
  });
  return { kind: 'ok' };
}
