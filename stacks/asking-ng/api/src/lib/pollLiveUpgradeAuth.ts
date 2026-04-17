import { createHash, timingSafeEqual } from 'node:crypto';
import type { IncomingMessage } from 'node:http';
import User from '../models/user.sequelize';
import { verifyToken } from '../utils/auth';
import { verifyEmbedReadToken } from './embedReadToken';
import { appEnv } from './env';

/** Same sources as HTTP public reads: query or `X-Poll-Embed-Token` on the upgrade request. */
export function readEmbedTokenFromUpgrade(req: IncomingMessage, url: URL): string | undefined {
  const q = url.searchParams.get('embed_token')?.trim();
  if (q) return q;
  const h = req.headers['x-poll-embed-token'];
  if (typeof h === 'string' && h.trim() !== '') return h.trim();
  if (Array.isArray(h) && typeof h[0] === 'string' && h[0].trim() !== '') return h[0].trim();
  return undefined;
}

/**
 * Browsers cannot set `Authorization` on `WebSocket`; use query **`ws_bearer`** with the same
 * user JWT as HTTP. Non-browser clients may send **`Authorization: Bearer`** on the upgrade.
 */
export function readWsBearerFromUpgrade(req: IncomingMessage, url: URL): string | undefined {
  const q = url.searchParams.get('ws_bearer')?.trim();
  if (q) return q;
  const auth = req.headers.authorization;
  if (typeof auth === 'string' && auth.toLowerCase().startsWith('bearer ')) {
    const t = auth.slice(7).trim();
    if (t) return t;
  }
  return undefined;
}

function verifySignedReadGrantFromUpgrade(url: URL, pollId: string): boolean {
  const expRaw = url.searchParams.get('embed_exp')?.trim() ?? '';
  const sig = url.searchParams.get('embed_sig')?.trim() ?? '';
  const expSec = Number(expRaw);
  const nowSec = Math.floor(Date.now() / 1000);
  if (!Number.isInteger(expSec) || expSec < nowSec || expSec - nowSec > 7 * 24 * 60 * 60)
    return false;
  const secret = appEnv.jwtSecret.trim();
  if (!secret || !sig) return false;
  const expected = createHash('sha256').update(`${secret}:v1:${pollId}:${expSec}`).digest('hex');
  const a = Buffer.from(expected, 'hex');
  const b = Buffer.from(sig, 'hex');
  if (a.length === 0 || a.length !== b.length) return false;
  try {
    return timingSafeEqual(a, b);
  } catch {
    return false;
  }
}

export async function pollLiveUpgradeAllowed(params: {
  pollId: string;
  url: URL;
  embedReadTokenHash: string | null | undefined;
  embedToken: string | undefined;
  creatorUserId: number | null | undefined;
  wsBearer: string | undefined;
}): Promise<boolean> {
  const { pollId, url, embedReadTokenHash, embedToken, creatorUserId, wsBearer } = params;
  if (verifyEmbedReadToken(embedReadTokenHash, embedToken)) return true;
  if (verifySignedReadGrantFromUpgrade(url, pollId)) return true;
  const raw = wsBearer?.trim();
  if (!raw) return false;
  const payload = verifyToken(raw);
  if (!payload) return false;
  if (creatorUserId == null || Number(payload.id) !== Number(creatorUserId)) return false;
  const user = await User.findByPk(payload.id, { attributes: ['active'] });
  if (!user) return false;
  return !!user.get('active');
}
