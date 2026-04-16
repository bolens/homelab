import type { AppRequest } from '../types/http';

export type RequestContext = {
  requestId: string | null;
  userId: number | null;
  homelab-user: string | null;
  role: string | null;
  ip: string | null;
};

export function getRequestContext(req: AppRequest): RequestContext {
  return {
    requestId: req.requestId ?? null,
    userId: req.user?.id ?? null,
    homelab-user: req.user?.homelab-user ?? null,
    role: req.user?.role ?? null,
    ip: typeof req.ip === 'string' && req.ip.trim() !== '' ? req.ip : null,
  };
}
