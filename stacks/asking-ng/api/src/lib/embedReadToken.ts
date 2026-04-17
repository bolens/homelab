import { createHash, randomBytes, timingSafeEqual } from 'node:crypto';
import type { AppRequest } from '../types/http';
import { appEnv } from './env';

/** Raw secret returned once at poll creation; only SHA-256 hex is stored. */
export function generateEmbedReadToken(): string {
  return randomBytes(24).toString('base64url');
}

export function hashEmbedReadToken(token: string): string {
  return createHash('sha256').update(token, 'utf8').digest('hex');
}

export function verifyEmbedReadToken(
  storedHash: string | null | undefined,
  providedToken: string | undefined,
): boolean {
  if (!storedHash || storedHash.trim() === '') return true;
  if (!providedToken || providedToken.trim() === '') return false;
  const a = Buffer.from(storedHash.trim(), 'hex');
  const b = Buffer.from(hashEmbedReadToken(providedToken.trim()), 'hex');
  if (a.length !== b.length || a.length === 0) return false;
  try {
    return timingSafeEqual(a, b);
  } catch {
    return false;
  }
}

export function readEmbedReadTokenFromRequest(req: AppRequest): string | undefined {
  const q = req.query?.['embed_token'];
  if (typeof q === 'string' && q.trim() !== '') return q.trim();
  if (Array.isArray(q) && typeof q[0] === 'string' && q[0].trim() !== '') return q[0].trim();
  const h = req.headers['x-poll-embed-token'];
  if (typeof h === 'string' && h.trim() !== '') return h.trim();
  if (Array.isArray(h) && typeof h[0] === 'string' && h[0].trim() !== '') return h[0].trim();
  return undefined;
}

/** Signed-in user is the poll creator (`creatorUserId` on the poll row). */
export function isPollOwnerRequest(
  req: AppRequest,
  creatorUserId: number | null | undefined,
): boolean {
  if (!req.user || creatorUserId == null) return false;
  return Number(req.user.id) === Number(creatorUserId);
}

/**
 * Public read paths that use the embed gate: valid token, no hash configured, or **poll owner**
 * with `Authorization: Bearer` (same `creatorUserId`). Does not apply to oEmbed (`/embed`) where
 * third-party fetchers have no session.
 */
export function pollEmbedReadAllowed(
  req: AppRequest,
  embedHash: string | null | undefined,
  embedToken: string | undefined,
  creatorUserId: number | null | undefined,
): boolean {
  return verifyEmbedReadToken(embedHash, embedToken) || isPollOwnerRequest(req, creatorUserId);
}

const MAX_SIGNED_EMBED_TTL_SECONDS = 7 * 24 * 60 * 60;
const MIN_SIGNED_EMBED_TTL_SECONDS = 30;

function embedSigningSecret(): string {
  return appEnv.jwtSecret.trim();
}

function buildEmbedGrantMaterial(pollId: string, expSec: number): string {
  return `v1:${pollId}:${expSec}`;
}

function signEmbedGrant(pollId: string, expSec: number): string {
  const secret = embedSigningSecret();
  if (!secret) return '';
  return createHash('sha256')
    .update(`${secret}:${buildEmbedGrantMaterial(pollId, expSec)}`)
    .digest('hex');
}

function verifyEmbedReadSignature(pollId: string, expSec: number, sig: string): boolean {
  const nowSec = Math.floor(Date.now() / 1000);
  if (!Number.isInteger(expSec) || expSec < nowSec) return false;
  if (expSec - nowSec > MAX_SIGNED_EMBED_TTL_SECONDS) return false;
  const expected = signEmbedGrant(pollId, expSec);
  if (!expected || !sig) return false;
  const a = Buffer.from(expected, 'hex');
  const b = Buffer.from(sig.trim(), 'hex');
  if (a.length === 0 || a.length !== b.length) return false;
  try {
    return timingSafeEqual(a, b);
  } catch {
    return false;
  }
}

function readSignedEmbedFields(req: AppRequest): { expSec: number; sig: string } | null {
  const expRaw = req.query?.['embed_exp'];
  const sigRaw = req.query?.['embed_sig'];
  const expValue =
    typeof expRaw === 'string'
      ? expRaw
      : Array.isArray(expRaw) && typeof expRaw[0] === 'string'
        ? expRaw[0]
        : '';
  const sigValue =
    typeof sigRaw === 'string'
      ? sigRaw
      : Array.isArray(sigRaw) && typeof sigRaw[0] === 'string'
        ? sigRaw[0]
        : '';
  const expSec = Number(expValue);
  if (!Number.isInteger(expSec) || !sigValue.trim()) return null;
  return { expSec, sig: sigValue.trim() };
}

export function pollSignedReadGrantAllowed(req: AppRequest, pollId: string): boolean {
  const fields = readSignedEmbedFields(req);
  if (!fields) return false;
  return verifyEmbedReadSignature(pollId, fields.expSec, fields.sig);
}

/** Read surface auth: embed token OR owner JWT OR signed short-lived read grant. */
export function pollEmbedViewAllowed(
  req: AppRequest,
  pollId: string,
  embedHash: string | null | undefined,
  embedToken: string | undefined,
  creatorUserId: number | null | undefined,
): boolean {
  if (pollEmbedReadAllowed(req, embedHash, embedToken, creatorUserId)) return true;
  return pollSignedReadGrantAllowed(req, pollId);
}

export function issueSignedEmbedReadGrant(
  pollId: string,
  ttlSeconds: number,
): { embed_exp: number; embed_sig: string } | null {
  const secret = embedSigningSecret();
  if (!secret) return null;
  const ttl = Math.min(
    MAX_SIGNED_EMBED_TTL_SECONDS,
    Math.max(MIN_SIGNED_EMBED_TTL_SECONDS, Math.floor(ttlSeconds)),
  );
  const expSec = Math.floor(Date.now() / 1000) + ttl;
  return {
    embed_exp: expSec,
    embed_sig: signEmbedGrant(pollId, expSec),
  };
}
