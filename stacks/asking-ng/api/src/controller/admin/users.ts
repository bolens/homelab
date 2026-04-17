import { jsonError } from '../../lib/jsonError';
import { getRequestContext } from '../../lib/requestContext';
import { invalidateSessionUserCache } from '../../lib/sessionUserCache';
import type { CreateUserBody, RolePatchBody, SetPasswordBody } from '../../schemas/admin';
import type { AppRequest, AppResponse } from '../../types/http';
import { singleString } from '../../utils/http';
import {
  presentDeletedUserMessage,
  presentPasswordResetMessage,
  presentUser,
  presentUsersList,
} from './users.presenter';
import {
  createUserService,
  deleteUserService,
  getUserService,
  listUsersService,
  patchUserRoleService,
  resetUserPasswordService,
} from './users.service';

export async function listUsersHandler(req: AppRequest, res: AppResponse): Promise<void> {
  const ctx = getRequestContext(req);
  const result = await listUsersService({ actorRole: ctx.role });
  if (result.kind === 'forbidden') {
    jsonError(res, req, 403, 'FORBIDDEN', 'Admin only');
    return;
  }
  res.json(presentUsersList({ users: result.users }));
}

export async function getUserHandler(req: AppRequest, res: AppResponse): Promise<void> {
  const ctx = getRequestContext(req);
  const result = await getUserService({
    actorRole: ctx.role,
    actorUserId: ctx.userId,
    userIdRaw: singleString(req.params.id) ?? null,
  });

  if (result.kind === 'invalid_id') {
    jsonError(res, req, 400, 'BAD_REQUEST', 'Invalid user id');
    return;
  }
  if (result.kind === 'forbidden') {
    jsonError(res, req, 403, 'FORBIDDEN', 'You can only view your own user record');
    return;
  }
  if (result.kind === 'not_found') {
    jsonError(res, req, 404, 'NOT_FOUND', 'User not found');
    return;
  }

  res.json(result.user);
}

export async function createUserHandler(req: AppRequest, res: AppResponse): Promise<void> {
  const ctx = getRequestContext(req);
  const result = await createUserService({
    actorRole: ctx.role,
    body: req.body as CreateUserBody,
  });

  if (result.kind === 'forbidden') {
    jsonError(res, req, 403, 'FORBIDDEN', 'Admin only');
    return;
  }
  if (result.kind === 'forbidden_superadmin') {
    jsonError(
      res,
      req,
      403,
      'FORBIDDEN',
      'Only superadmin can create users with the superadmin role',
    );
    return;
  }

  res.status(201).json(presentUser({ user: result.user }));
}

export async function deleteUserHandler(req: AppRequest, res: AppResponse): Promise<void> {
  const ctx = getRequestContext(req);
  const result = await deleteUserService({
    actorRole: ctx.role,
    userIdRaw: singleString(req.params.id) ?? null,
  });

  if (result.kind === 'forbidden') {
    jsonError(res, req, 403, 'FORBIDDEN', 'Admin only');
    return;
  }
  if (result.kind === 'invalid_id') {
    jsonError(res, req, 400, 'BAD_REQUEST', 'Invalid user id');
    return;
  }
  if (result.kind === 'not_found') {
    jsonError(res, req, 404, 'NOT_FOUND', 'User not found');
    return;
  }

  invalidateSessionUserCache(result.deletedId);
  res.json(presentDeletedUserMessage(result.deletedId));
}

export async function patchUserRoleHandler(req: AppRequest, res: AppResponse): Promise<void> {
  const ctx = getRequestContext(req);
  const result = await patchUserRoleService({
    actorRole: ctx.role,
    userIdRaw: singleString(req.params.id) ?? null,
    body: req.body as RolePatchBody,
  });

  if (result.kind === 'forbidden') {
    jsonError(res, req, 403, 'FORBIDDEN', 'Admin only');
    return;
  }
  if (result.kind === 'invalid_id') {
    jsonError(res, req, 400, 'BAD_REQUEST', 'Invalid user id');
    return;
  }
  if (result.kind === 'not_found') {
    jsonError(res, req, 404, 'NOT_FOUND', 'User not found');
    return;
  }
  if (result.kind === 'forbidden_modify_superadmin') {
    jsonError(res, req, 403, 'FORBIDDEN', 'Only superadmin can modify a superadmin account');
    return;
  }
  if (result.kind === 'forbidden_assign_superadmin') {
    jsonError(res, req, 403, 'FORBIDDEN', 'Only superadmin can assign the superadmin role');
    return;
  }

  invalidateSessionUserCache(result.updatedId);
  res.json(presentUser({ user: result.user }));
}

export async function resetUserPasswordHandler(req: AppRequest, res: AppResponse): Promise<void> {
  const ctx = getRequestContext(req);
  const result = await resetUserPasswordService({
    actorRole: ctx.role,
    userIdRaw: singleString(req.params.id) ?? null,
    body: req.body as SetPasswordBody,
  });

  if (result.kind === 'forbidden') {
    jsonError(res, req, 403, 'FORBIDDEN', 'Admin only');
    return;
  }
  if (result.kind === 'invalid_id') {
    jsonError(res, req, 400, 'BAD_REQUEST', 'Invalid user id');
    return;
  }
  if (result.kind === 'not_found') {
    jsonError(res, req, 404, 'NOT_FOUND', 'User not found');
    return;
  }

  invalidateSessionUserCache(result.updatedId);
  res.json(presentPasswordResetMessage());
}
