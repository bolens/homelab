import { jsonError } from '../../lib/jsonError';
import { getRequestContext } from '../../lib/requestContext';
import { invalidateSessionUserCache } from '../../lib/sessionUserCache';
import type { ProfileUpdateBody } from '../../schemas/profile';
import type { SelfPasswordChangeBody } from '../../schemas/userSelf';
import type { AppRequest, AppResponse } from '../../types/http';
import { presentPasswordUpdated, presentProfile } from './self.presenter';
import { getProfileService, updateProfileService, updateSelfPasswordService } from './self.service';

export async function getProfileHandler(req: AppRequest, res: AppResponse): Promise<void> {
  const ctx = getRequestContext(req);
  const result = await getProfileService({ userId: ctx.userId });
  if (result.kind === 'not_found') {
    jsonError(res, req, 404, 'NOT_FOUND', 'User not found');
    return;
  }
  res.json(presentProfile({ user: result.user }));
}

export async function updateProfileHandler(req: AppRequest, res: AppResponse): Promise<void> {
  const ctx = getRequestContext(req);
  const result = await updateProfileService({
    userId: ctx.userId,
    body: req.body as ProfileUpdateBody,
  });
  if (result.kind === 'not_found') {
    jsonError(res, req, 404, 'NOT_FOUND', 'User not found');
    return;
  }
  invalidateSessionUserCache(ctx.userId!);
  res.json(presentProfile({ user: result.user }));
}

export async function updateSelfPasswordHandler(req: AppRequest, res: AppResponse): Promise<void> {
  const ctx = getRequestContext(req);
  const result = await updateSelfPasswordService({
    userId: ctx.userId,
    body: req.body as SelfPasswordChangeBody,
  });

  if (result.kind === 'not_found') {
    jsonError(res, req, 404, 'NOT_FOUND', 'User not found');
    return;
  }
  if (result.kind === 'invalid_credentials') {
    jsonError(res, req, 401, 'UNAUTHORIZED', 'Invalid credentials');
    return;
  }

  invalidateSessionUserCache(ctx.userId!);
  res.json(presentPasswordUpdated());
}
