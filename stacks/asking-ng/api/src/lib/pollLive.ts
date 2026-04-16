import type { IncomingMessage, Server } from 'node:http';
import type { Duplex } from 'node:stream';
import { WebSocket, WebSocketServer } from 'ws';
import { appEnv } from './env';
import {
  clearPollLiveRoomCreatorForFanout,
  prunePollLiveFanoutLimiter,
  setPollLiveRoomCreatorForFanout,
  takePollLiveFanoutOrShed,
} from './billingWsFanout';
import { resolveEffectivePollLiveRoomCap } from './billingWsQuota';
import Poll from '../model/Poll';
import { logger } from './logger';
import { matchPollLivePath } from './pollLivePath';
import {
  pollLiveUpgradeAllowed,
  readEmbedTokenFromUpgrade,
  readWsBearerFromUpgrade,
} from './pollLiveUpgradeAuth';
import {
  buildWsAllowedOriginSet,
  clientIpForUpgrade,
  isWsOriginAllowed,
  SlidingWindowRateLimit,
} from './pollWsGuards';

const rooms = new Map<string, Set<WebSocket>>();

type PollLivePayload = { type: 'update' } | { type: 'deleted' } | { type: 'panic' };

function roomFor(pollId: string): Set<WebSocket> {
  let set = rooms.get(pollId);
  if (!set) {
    set = new Set();
    rooms.set(pollId, set);
  }
  return set;
}

function detach(pollId: string, ws: WebSocket): void {
  const set = rooms.get(pollId);
  if (!set) return;
  set.delete(ws);
  if (set.size === 0) {
    rooms.delete(pollId);
    clearPollLiveRoomCreatorForFanout(pollId);
  }
}

/** Push JSON to every subscriber for this poll (public viewers + admins watching results). */
export function notifyPollLive(pollId: string, payload: PollLivePayload): void {
  const set = rooms.get(pollId);
  if (!set || set.size === 0) return;
  const sheddable = payload.type === 'update';
  if (sheddable && !takePollLiveFanoutOrShed(pollId)) return;
  const body = JSON.stringify(payload);
  for (const ws of set) {
    if (ws.readyState === WebSocket.OPEN) {
      try {
        ws.send(body);
      } catch (err: unknown) {
        logger.warn({ event: 'poll.live.send_failed', err, pollId }, 'poll live send failed');
      }
    }
  }
}

/**
 * WebSocket hub on the same HTTP server as the API (Fastify). Path: `GET /ws/poll/:pollId` with optional
 * `embed_token` / `X-Poll-Embed-Token`, or **`ws_bearer`** / `Authorization: Bearer` for poll owners
 * on gated polls. Clients should refetch poll JSON on `{ type: 'update' }` or `{ type: 'panic' }`;
 * on `{ type: 'deleted' }` expect 404.
 *
 * Hardening (env-driven):
 * - Origin: if `WS_ALLOWED_ORIGINS` or `CORS_ORIGIN` yields a non-empty list, require matching `Origin` (unless `WS_ALLOW_MISSING_ORIGIN=true`).
 * - Rate limit: per-IP upgrade attempts per window (`WS_UPGRADE_MAX_PER_IP`, `WS_UPGRADE_WINDOW_MS`).
 * - Room cap: `min(WS_MAX_SUBSCRIBERS_PER_POLL, plan tier)` when `BILLING_ENFORCE_LIMITS`, else env only.
 * - Outbound fanout: `min(WS_FANOUT_MAX_PER_POLL_PER_SEC, plan tier)` messages/s per poll; excess `notifyPollLive` bursts are dropped (see `billingWsFanout.ts`).
 * - Client messages are rejected (server-push only); small `maxPayload`.
 */
export function attachPollLiveWss(server: Server): void {
  const allowedOrigins = buildWsAllowedOriginSet();
  const allowMissingOrigin = appEnv.wsAllowMissingOrigin;
  const upgradeMax = appEnv.wsUpgradeMaxPerIp;
  const upgradeWindowMs = appEnv.wsUpgradeWindowMs;

  const upgradeLimiter = new SlidingWindowRateLimit(upgradeMax, upgradeWindowMs);
  let pruneCounter = 0;
  let fanoutPruneCounter = 0;

  const wss = new WebSocketServer({
    noServer: true,
    maxPayload: 128,
    perMessageDeflate: false,
  });

  server.on('upgrade', (req: IncomingMessage, socket: Duplex, head: Buffer) => {
    void (async () => {
      try {
        const host = req.headers.host ?? 'localhost';
        const url = new URL(req.url ?? '/', `http://${host}`);
        const pollId = matchPollLivePath(url.pathname);
        if (!pollId) {
          socket.destroy();
          return;
        }

        const embedToken = readEmbedTokenFromUpgrade(req, url);
        const wsBearer = readWsBearerFromUpgrade(req, url);
        const poll = await Poll.findByPk(pollId, {
          attributes: ['embedReadTokenHash', 'creatorUserId'],
        });
        if (!poll) {
          socket.destroy();
          return;
        }
        const embedHash = poll.get('embedReadTokenHash') as string | null | undefined;
        const creatorUserId = poll.get('creatorUserId') as number | null | undefined;
        const allowed = await pollLiveUpgradeAllowed({
          pollId,
          url,
          embedReadTokenHash: embedHash,
          embedToken,
          creatorUserId,
          wsBearer,
        });
        if (!allowed) {
          logger.debug(
            { event: 'poll.live.ws.auth_rejected', pollId },
            'poll live ws: embed or owner auth rejected',
          );
          socket.destroy();
          return;
        }

        const origin = req.headers.origin;
        if (!isWsOriginAllowed(origin, allowedOrigins, allowMissingOrigin)) {
          logger.debug(
            { event: 'poll.live.ws.origin_rejected', origin, pollId },
            'poll live ws: origin rejected',
          );
          socket.destroy();
          return;
        }

        const ip = clientIpForUpgrade(req);
        if (!upgradeLimiter.take(ip)) {
          logger.debug(
            { event: 'poll.live.ws.upgrade_rate_limited', ip, pollId },
            'poll live ws: upgrade rate limited',
          );
          socket.destroy();
          return;
        }

        const roomCap = await resolveEffectivePollLiveRoomCap(creatorUserId);

        pruneCounter += 1;
        if (pruneCounter >= 256) {
          pruneCounter = 0;
          upgradeLimiter.pruneStale();
        }
        fanoutPruneCounter += 1;
        if (fanoutPruneCounter >= 256) {
          fanoutPruneCounter = 0;
          prunePollLiveFanoutLimiter();
        }

        wss.handleUpgrade(req, socket, head, (ws) => {
          const set = roomFor(pollId);
          if (set.size >= roomCap) {
            try {
              ws.close(1008, 'USAGE_LIMIT_WS_SUBSCRIBERS');
            } catch {
              /* ignore */
            }
            return;
          }
          setPollLiveRoomCreatorForFanout(pollId, creatorUserId);
          set.add(ws);
          ws.on('message', () => {
            try {
              ws.close(1008, 'server-push only');
            } catch {
              /* ignore */
            }
          });
          ws.on('close', () => detach(pollId, ws));
          ws.on('error', (err) => {
            logger.warn({ event: 'poll.live.ws.socket_error', err, pollId }, 'poll live ws error');
          });
        });
      } catch (err: unknown) {
        logger.warn({ event: 'poll.live.ws.upgrade_failed', err }, 'poll live upgrade failed');
        socket.destroy();
      }
    })();
  });

  const pruneIntervalMs = Math.min(upgradeWindowMs, 120_000);
  const iv = setInterval(() => upgradeLimiter.pruneStale(), pruneIntervalMs);
  iv.unref?.();
}
