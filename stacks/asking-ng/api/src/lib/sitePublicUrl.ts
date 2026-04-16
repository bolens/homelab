import type { AppRequest } from '../types/http';
import { appEnv } from './env';

/** Canonical public site origin for poll page + oEmbed (no trailing slash). */
function configuredPublicSiteOrigin(): string {
  const u = appEnv.publicSiteUrl;
  if (u) return u;
  const cors = appEnv.corsOrigins[0]?.trim().replace(/\/$/, '');
  return cors ?? '';
}

/** Fallback when `PUBLIC_SITE_URL` / `CORS_ORIGIN` unset: use forwarded or Host (best effort). */
function inferRequestPublicOrigin(req: AppRequest): string {
  const xfProto = req.headers['x-forwarded-proto'];
  const xfHost = req.headers['x-forwarded-host'];
  const proto =
    (typeof xfProto === 'string' ? xfProto.split(',')[0]?.trim() : undefined) ||
    (req.secure ? 'https' : 'http');
  const host =
    (typeof xfHost === 'string' ? xfHost.split(',')[0]?.trim() : undefined) ||
    req.headers.host ||
    'localhost';
  return `${proto}://${host}`;
}

export function publicSiteRoot(req: AppRequest): string {
  const configured = configuredPublicSiteOrigin();
  return configured || inferRequestPublicOrigin(req);
}

export function publicPollPageUrl(req: AppRequest, pollId: string): string {
  return `${publicSiteRoot(req).replace(/\/$/, '')}/${encodeURIComponent(pollId)}`;
}

export function publicPollResultsUrl(req: AppRequest, pollId: string): string {
  return `${publicSiteRoot(req).replace(/\/$/, '')}/${encodeURIComponent(pollId)}/results`;
}
