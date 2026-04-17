import { jsonError } from '../lib/jsonError';
import {
  getSessionUserFromCache,
  type SessionUserSnapshot,
  setSessionUserCache,
} from '../lib/sessionUserCache';
import User from '../models/user.sequelize';
import type { AppRequest, AppRequestHandler, AppResponse } from '../types/http';
import { verifyToken } from '../utils/auth';

/**
 * Validates Bearer JWT when `res` is set, writes JSON errors and returns false.
 * When `res` is null (optional attach), returns false without writing.
 */
export async function authenticateBearer(
  req: AppRequest,
  res: AppResponse | null,
): Promise<boolean> {
  const authHeader = req.headers.authorization;
  if (!authHeader) {
    if (res) jsonError(res, req, 401, 'MISSING_AUTHORIZATION', 'Missing Authorization header');
    return false;
  }
  const token = authHeader.split(' ')[1];
  if (!token) {
    if (res) jsonError(res, req, 401, 'MISSING_TOKEN', 'Missing bearer token');
    return false;
  }
  const payload = verifyToken(token);
  if (!payload) {
    if (res) jsonError(res, req, 401, 'INVALID_TOKEN', 'Invalid or expired token');
    return false;
  }

  const cached = getSessionUserFromCache(payload.id);
  if (cached && cached.id === payload.id) {
    req.user = {
      id: cached.id,
      homelab-user: cached.homelab-user,
      role: cached.role,
      billingPlan: cached.billingPlan,
    };
    return true;
  }

  const user = await User.findByPk(payload.id, {
    attributes: ['id', 'homelab-user', 'role', 'active', 'billingPlan'],
  });
  if (!user) {
    if (res) jsonError(res, req, 401, 'INVALID_TOKEN', 'User no longer exists');
    return false;
  }
  const active = !!user.get('active');
  if (!active) {
    if (res) jsonError(res, req, 403, 'ACCOUNT_DISABLED', 'Account is suspended.');
    return false;
  }

  const billingPlan = String(user.get('billingPlan') ?? 'free').trim() || 'free';
  const snapshot: SessionUserSnapshot = {
    id: user.get('id') as number,
    homelab-user: user.get('homelab-user') as string,
    role: user.get('role') as string,
    active,
    billingPlan,
  };
  setSessionUserCache(snapshot);

  req.user = {
    id: snapshot.id,
    homelab-user: snapshot.homelab-user,
    role: snapshot.role,
    billingPlan: snapshot.billingPlan,
  };
  return true;
}

/**
 * Validates Bearer JWT, loads the user from the database, and rejects inactive accounts.
 * Sets {@link AppRequest.user} from the DB (role matches current server state).
 */
export const requireSession: AppRequestHandler = (req, res, next) => {
  void authenticateBearer(req, res)
    .then((ok) => {
      if (ok) next();
    })
    .catch(next);
};

/** If `Authorization: Bearer` is valid, sets `req.user`; otherwise continues without error. */
export const optionalSession: AppRequestHandler = (req, _res, next) => {
  void authenticateBearer(req, null)
    .then(() => next())
    .catch(next);
};

export function isJwtAdminRole(role: string): boolean {
  return role === 'admin' || role === 'superadmin';
}
