import { getStoredUserJwt } from './userSession';

/** Decode JWT payload (second segment) without verifying the signature — routing hints only. */
function readJwtPayloadUnverified(token: string): Record<string, unknown> | null {
  try {
    const parts = token.split('.');
    if (parts.length !== 3 || !parts[1]) return null;
    const seg = parts[1];
    const pad = seg + '='.repeat((4 - (seg.length % 4)) % 4);
    const b64 = pad.replace(/-/g, '+').replace(/_/g, '/');
    const json = atob(b64);
    return JSON.parse(json) as Record<string, unknown>;
  } catch {
    return null;
  }
}

function jwtExpMs(exp: unknown): number | null {
  if (typeof exp !== 'number' || !Number.isFinite(exp)) return null;
  return exp * 1000;
}

/** True if token parses as a non-expired admin or superadmin JWT (signature not verified). */
function isLikelyAdminRoleJwt(token: string | null | undefined): boolean {
  if (!token?.trim()) return false;
  const payload = readJwtPayloadUnverified(token.trim());
  if (!payload) return false;
  const expMs = jwtExpMs(payload['exp']);
  if (expMs != null && expMs <= Date.now()) return false;
  const role = payload['role'];
  return role === 'admin' || role === 'superadmin';
}

/** Stored credentials that may unlock `/admin` in the router (server still validates). */
export function hasAdminRouteCredential(): boolean {
  if (typeof window === 'undefined') return false;
  try {
    if (localStorage.getItem('adminToken')?.trim()) return true;
  } catch {
    /* private mode */
  }
  return isLikelyAdminRoleJwt(getStoredUserJwt());
}
