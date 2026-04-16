import type { CreateUserBody, RolePatchBody, SetPasswordBody } from '../../schemas/admin';
import { ensureDefaultWorkspaceForUser } from '../../lib/workspaceBootstrap';
import { hashPassword } from '../../utils/auth';
import {
  createUserRecord,
  deleteUserById,
  findUserById,
  findUserSummaryById,
  listUsers,
} from './users.repository';

type UserSummary = {
  id: number;
  homelab-user: string;
  role: string;
};

function toUserSummary(user: { get(key: 'id' | 'homelab-user' | 'role'): unknown }): UserSummary {
  return {
    id: user.get('id') as number,
    homelab-user: user.get('homelab-user') as string,
    role: user.get('role') as string,
  };
}

type AdminAuthArgs = {
  actorRole: string | null;
};

function isAdmin(role: string | null): boolean {
  return role === 'admin' || role === 'superadmin';
}

export type ListUsersResult = { kind: 'forbidden' } | { kind: 'ok'; users: UserSummary[] };

export async function listUsersService(args: AdminAuthArgs): Promise<ListUsersResult> {
  if (!isAdmin(args.actorRole)) return { kind: 'forbidden' };

  const users = await listUsers();
  return { kind: 'ok', users: users.map((user) => toUserSummary(user)) };
}

export type GetUserResult =
  | { kind: 'invalid_id' }
  | { kind: 'forbidden' }
  | { kind: 'not_found' }
  | { kind: 'ok'; user: UserSummary };

export async function getUserService(args: {
  actorRole: string | null;
  actorUserId: number | null;
  userIdRaw: string | null;
}): Promise<GetUserResult> {
  const id = Number.parseInt(args.userIdRaw ?? '', 10);
  if (!Number.isFinite(id) || id < 1) return { kind: 'invalid_id' };

  if (!isAdmin(args.actorRole) && id !== args.actorUserId) return { kind: 'forbidden' };

  const user = await findUserSummaryById(id);
  if (!user) return { kind: 'not_found' };

  return { kind: 'ok', user: toUserSummary(user) };
}

export type CreateUserResult =
  | { kind: 'forbidden' }
  | { kind: 'forbidden_superadmin' }
  | { kind: 'ok'; user: UserSummary };

export async function createUserService(args: {
  actorRole: string | null;
  body: CreateUserBody;
}): Promise<CreateUserResult> {
  if (!isAdmin(args.actorRole)) return { kind: 'forbidden' };

  const effectiveRole = args.body.role ?? 'user';
  if (effectiveRole === 'superadmin' && args.actorRole !== 'superadmin') {
    return { kind: 'forbidden_superadmin' };
  }

  const user = await createUserRecord({
    homelab-user: args.body.homelab-user,
    password: hashPassword(args.body.password),
    role: effectiveRole,
  });
  await ensureDefaultWorkspaceForUser(user);

  return { kind: 'ok', user: toUserSummary(user) };
}

export type DeleteUserResult =
  | { kind: 'invalid_id' }
  | { kind: 'forbidden' }
  | { kind: 'not_found' }
  | { kind: 'ok'; deletedId: number };

export async function deleteUserService(args: {
  actorRole: string | null;
  userIdRaw: string | null;
}): Promise<DeleteUserResult> {
  if (!isAdmin(args.actorRole)) return { kind: 'forbidden' };

  const id = Number.parseInt(args.userIdRaw ?? '', 10);
  if (!Number.isFinite(id) || id < 1) return { kind: 'invalid_id' };

  const deleted = await deleteUserById(id);
  if (!deleted) return { kind: 'not_found' };

  return { kind: 'ok', deletedId: id };
}

export type PatchUserRoleResult =
  | { kind: 'invalid_id' }
  | { kind: 'forbidden' }
  | { kind: 'not_found' }
  | { kind: 'forbidden_modify_superadmin' }
  | { kind: 'forbidden_assign_superadmin' }
  | { kind: 'ok'; user: UserSummary; updatedId: number };

export async function patchUserRoleService(args: {
  actorRole: string | null;
  userIdRaw: string | null;
  body: RolePatchBody;
}): Promise<PatchUserRoleResult> {
  if (!isAdmin(args.actorRole)) return { kind: 'forbidden' };

  const id = Number.parseInt(args.userIdRaw ?? '', 10);
  if (!Number.isFinite(id) || id < 1) return { kind: 'invalid_id' };

  const user = await findUserById(id);
  if (!user) return { kind: 'not_found' };

  const priorRole = user.get('role') as string;
  if (priorRole === 'superadmin' && args.actorRole !== 'superadmin') {
    return { kind: 'forbidden_modify_superadmin' };
  }
  if (args.body.role === 'superadmin' && args.actorRole !== 'superadmin') {
    return { kind: 'forbidden_assign_superadmin' };
  }

  user.set('role', args.body.role);
  await user.save();

  return { kind: 'ok', user: toUserSummary(user), updatedId: id };
}

export type ResetPasswordResult =
  | { kind: 'invalid_id' }
  | { kind: 'forbidden' }
  | { kind: 'not_found' }
  | { kind: 'ok'; updatedId: number };

export async function resetUserPasswordService(args: {
  actorRole: string | null;
  userIdRaw: string | null;
  body: SetPasswordBody;
}): Promise<ResetPasswordResult> {
  if (!isAdmin(args.actorRole)) return { kind: 'forbidden' };

  const id = Number.parseInt(args.userIdRaw ?? '', 10);
  if (!Number.isFinite(id) || id < 1) return { kind: 'invalid_id' };

  const user = await findUserById(id);
  if (!user) return { kind: 'not_found' };

  user.set('password', hashPassword(args.body.password));
  await user.save();

  return { kind: 'ok', updatedId: id };
}
